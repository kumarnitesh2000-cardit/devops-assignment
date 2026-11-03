import json
import os
from decimal import Decimal
from functools import lru_cache
from typing import Any, Literal, Optional, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field


DocumentType = Literal[
    "claim_forms",
    "cheque_or_bank_details",
    "identity_document",
    "itemized_bill",
    "discharge_summary",
    "prescription",
    "investigation_report",
    "cash_receipt",
    "other",
]

EXTRACTION_TYPES = {
    "identity_document",
    "discharge_summary",
    "itemized_bill",
}


class PageClassification(BaseModel):
    page_number: int = Field(description="One-based page number from the supplied PDF")
    document_type: DocumentType


class PageClassifications(BaseModel):
    pages: list[PageClassification]


class IdentityNumber(BaseModel):
    kind: Optional[str] = None
    value: Optional[str] = None


class IdentityExtraction(BaseModel):
    patient_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    identity_numbers: list[IdentityNumber] = Field(default_factory=list)
    policy_number: Optional[str] = None
    insurer: Optional[str] = None


class DischargeExtraction(BaseModel):
    diagnosis: Optional[str] = None
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    physician_name: Optional[str] = None
    physician_details: Optional[str] = None


class BillItem(BaseModel):
    description: str
    quantity: Optional[float] = None
    amount: float


class BillExtraction(BaseModel):
    items: list[BillItem] = Field(default_factory=list)


class ClaimState(TypedDict, total=False):
    claim_id: str
    pages: list[dict[str, Any]]
    segregated_pages: list[dict[str, Any]]
    identity: dict[str, Any]
    discharge_summary: dict[str, Any]
    itemized_bill: dict[str, Any]
    result: dict[str, Any]


class AgentInput(TypedDict):
    claim_id: str
    pages: list[dict[str, Any]]


@lru_cache(maxsize=1)
def _get_chat_model() -> ChatOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required to process claims")
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=api_key,
        temperature=0,
    )


def _invoke_structured(
    schema: type[BaseModel], prompt: str, chat_model: Any = None
) -> BaseModel:
    model = chat_model if chat_model is not None else _get_chat_model()
    response = model.with_structured_output(schema).invoke(prompt)
    if isinstance(response, schema):
        return response
    return schema.model_validate(response)


def _page_payload(pages: list[dict[str, Any]]) -> str:
    return json.dumps(
        [{"page_number": page["page_number"], "text": page["text"]} for page in pages],
        ensure_ascii=False,
    )


def build_claim_graph(chat_model: Any = None):
    """Build the claim graph. `chat_model` can be injected for tests."""

    def segregator(state: ClaimState) -> dict[str, Any]:
        pages = state["pages"]
        batch_size = max(1, int(os.getenv("SEGREGATION_BATCH_SIZE", "8")))
        classifications: dict[int, str] = {}

        for start in range(0, len(pages), batch_size):
            batch = pages[start : start + batch_size]
            prompt = (
                "Classify every supplied PDF page into exactly one document_type: "
                "claim_forms, cheque_or_bank_details, identity_document, itemized_bill, "
                "discharge_summary, prescription, investigation_report, cash_receipt, or other. "
                "Use page numbers exactly as supplied. Do not omit a page. "
                "Return only the structured classification.\nPAGES_JSON:\n"
                f"{_page_payload(batch)}"
            )
            result = _invoke_structured(PageClassifications, prompt, chat_model)
            expected = {page["page_number"] for page in batch}
            found = [entry.page_number for entry in result.pages]
            if len(found) != len(set(found)) or set(found) != expected:
                raise ValueError("Segregator must classify each supplied page exactly once")
            classifications.update(
                {entry.page_number: entry.document_type for entry in result.pages}
            )

        classified = [
            {**page, "document_type": classifications[page["page_number"]]}
            for page in pages
        ]
        return {"segregated_pages": classified}

    def route_to_agents(state: ClaimState) -> list[Send]:
        assigned = state["segregated_pages"]
        return [
            Send(
                "id_agent",
                {
                    "claim_id": state["claim_id"],
                    "pages": [
                        page for page in assigned if page["document_type"] == "identity_document"
                    ],
                },
            ),
            Send(
                "discharge_summary_agent",
                {
                    "claim_id": state["claim_id"],
                    "pages": [
                        page
                        for page in assigned
                        if page["document_type"] == "discharge_summary"
                    ],
                },
            ),
            Send(
                "itemized_bill_agent",
                {
                    "claim_id": state["claim_id"],
                    "pages": [page for page in assigned if page["document_type"] == "itemized_bill"],
                },
            ),
        ]

    def id_agent(agent_input: AgentInput) -> dict[str, Any]:
        if not agent_input["pages"]:
            return {"identity": IdentityExtraction().model_dump()}
        prompt = (
            "Extract only identity and policy information visible in these assigned identity pages. "
            "Do not infer missing values; use null or an empty list. Preserve dates as printed. "
            "Return the requested structured fields.\nASSIGNED_PAGES_JSON:\n"
            f"{_page_payload(agent_input['pages'])}"
        )
        result = _invoke_structured(IdentityExtraction, prompt, chat_model)
        return {"identity": result.model_dump()}

    def discharge_summary_agent(agent_input: AgentInput) -> dict[str, Any]:
        if not agent_input["pages"]:
            return {"discharge_summary": DischargeExtraction().model_dump()}
        prompt = (
            "Extract diagnosis, admission and discharge dates, physician name, and physician details "
            "only from these assigned discharge summary pages. Do not infer missing values; use null. "
            "Preserve dates as printed. Return the requested structured fields."
            "\nASSIGNED_PAGES_JSON:\n"
            f"{_page_payload(agent_input['pages'])}"
        )
        result = _invoke_structured(DischargeExtraction, prompt, chat_model)
        return {"discharge_summary": result.model_dump()}

    def itemized_bill_agent(agent_input: AgentInput) -> dict[str, Any]:
        if not agent_input["pages"]:
            return {"itemized_bill": {"items": [], "total_amount": 0.0}}
        prompt = (
            "Extract every billed line item from only these assigned itemized bill pages. "
            "Each item amount must be the line total as printed, not a unit price unless that is "
            "the only amount shown. Do not include subtotals as line items. Return structured items."
            "\nASSIGNED_PAGES_JSON:\n"
            f"{_page_payload(agent_input['pages'])}"
        )
        result = _invoke_structured(BillExtraction, prompt, chat_model)
        total = sum((Decimal(str(item.amount)) for item in result.items), Decimal("0"))
        return {
            "itemized_bill": {
                "items": [item.model_dump() for item in result.items],
                "total_amount": float(total),
            }
        }

    def aggregator(state: ClaimState) -> dict[str, Any]:
        return {
            "result": {
                "claim_id": state["claim_id"],
                "page_classifications": [
                    {
                        "page_number": page["page_number"],
                        "document_type": page["document_type"],
                    }
                    for page in state["segregated_pages"]
                ],
                "identity": state["identity"],
                "discharge_summary": state["discharge_summary"],
                "itemized_bill": state["itemized_bill"],
            }
        }

    graph = StateGraph(ClaimState)
    graph.add_node("segregator", segregator)
    graph.add_node("id_agent", id_agent)
    graph.add_node("discharge_summary_agent", discharge_summary_agent)
    graph.add_node("itemized_bill_agent", itemized_bill_agent)
    graph.add_node("aggregator", aggregator)
    graph.add_edge(START, "segregator")
    graph.add_conditional_edges("segregator", route_to_agents)
    graph.add_edge(
        ["id_agent", "discharge_summary_agent", "itemized_bill_agent"],
        "aggregator",
    )
    graph.add_edge("aggregator", END)
    return graph.compile()


claim_graph = build_claim_graph()


def process_claim(claim_id: str, pages: list[dict[str, Any]]) -> dict[str, Any]:
    state = claim_graph.invoke({"claim_id": claim_id, "pages": pages})
    return state["result"]