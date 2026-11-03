import json
import unittest

from claims_pipeline.workflow import (
    BillExtraction,
    BillItem,
    DischargeExtraction,
    IdentityExtraction,
    PageClassification,
    PageClassifications,
    build_claim_graph,
)


class FakeStructuredRunnable:
    def __init__(self, owner, schema):
        self.owner = owner
        self.schema = schema

    def invoke(self, prompt):
        self.owner.calls.append((self.schema.__name__, prompt))
        if self.schema is PageClassifications:
            pages = json.loads(prompt.split("PAGES_JSON:\n", 1)[1])
            return PageClassifications(
                pages=[
                    PageClassification(
                        page_number=page["page_number"],
                        document_type=self._classify(page["text"]),
                    )
                    for page in pages
                ]
            )
        if self.schema is IdentityExtraction:
            return IdentityExtraction(patient_name="Jordan Example", policy_number="P-123")
        if self.schema is DischargeExtraction:
            return DischargeExtraction(
                diagnosis="Example diagnosis",
                admission_date="2026-01-02",
                discharge_date="2026-01-04",
            )
        if self.schema is BillExtraction:
            return BillExtraction(
                items=[
                    BillItem(description="Room charge", quantity=2, amount=80.25),
                    BillItem(description="Medicine", quantity=1, amount=19.75),
                ]
            )
        raise AssertionError("Unexpected structured output schema: %s" % self.schema)

    @staticmethod
    def _classify(text):
        if "IDENTITY_PAGE" in text:
            return "identity_document"
        if "DISCHARGE_PAGE" in text:
            return "discharge_summary"
        if "BILL_PAGE" in text:
            return "itemized_bill"
        if "BANK_PAGE" in text:
            return "cheque_or_bank_details"
        return "other"


class FakeChatModel:
    def __init__(self):
        self.calls = []

    def with_structured_output(self, schema):
        return FakeStructuredRunnable(self, schema)


class ClaimWorkflowTests(unittest.TestCase):
    def test_routes_only_assigned_pages_and_aggregates_results(self):
        model = FakeChatModel()
        graph = build_claim_graph(chat_model=model)
        state = graph.invoke(
            {
                "claim_id": "claim-42",
                "pages": [
                    {"page_number": 1, "text": "IDENTITY_PAGE Jordan Example"},
                    {"page_number": 2, "text": "DISCHARGE_PAGE diagnosis"},
                    {"page_number": 3, "text": "BILL_PAGE room and medicine"},
                    {"page_number": 4, "text": "BANK_PAGE account number"},
                ],
            }
        )

        result = state["result"]
        self.assertEqual(result["claim_id"], "claim-42")
        self.assertEqual(
            [page["document_type"] for page in result["page_classifications"]],
            [
                "identity_document",
                "discharge_summary",
                "itemized_bill",
                "cheque_or_bank_details",
            ],
        )
        self.assertEqual(result["identity"]["patient_name"], "Jordan Example")
        self.assertEqual(result["discharge_summary"]["diagnosis"], "Example diagnosis")
        self.assertEqual(result["itemized_bill"]["total_amount"], 100.0)

        agent_prompts = {
            name: prompt
            for name, prompt in model.calls
            if name != "PageClassifications"
        }
        self.assertIn("IDENTITY_PAGE", agent_prompts["IdentityExtraction"])
        self.assertNotIn("BANK_PAGE", agent_prompts["IdentityExtraction"])
        self.assertIn("DISCHARGE_PAGE", agent_prompts["DischargeExtraction"])
        self.assertNotIn("IDENTITY_PAGE", agent_prompts["DischargeExtraction"])
        self.assertIn("BILL_PAGE", agent_prompts["BillExtraction"])
        self.assertNotIn("BANK_PAGE", agent_prompts["BillExtraction"])


if __name__ == "__main__":
    unittest.main()