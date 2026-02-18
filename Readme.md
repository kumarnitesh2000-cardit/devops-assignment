## DevOps Assessment Assignment

# Architecture Diagram 
![Alt text]([image-url](https://github.com/kumarnitesh2000-cardit/devops-assignment/diagram.jpg))

#Instructions
```
To run locally:

- Clone or download the git hub repo
- Open index.html under frontend folder
- Open a terminal in the main directory and run command:
  `docker compose up`
- This docker compose have all 3 services (redis,worker and backend) as docker containers
- Type `docker ps` to get a list of all the containers running and type `docker exec -it my_container_name sh` to exec into it
- The env are entered into the compose file for local purposes only, it is not pushed to git (added to .gitignore). GitHub actions sends the
  env and secrets data to the containers.

```
#Journey
```
### Fill Complete Journey

Locally:

- Forked the project and tried running locally
- Learnt that celery has issues with windows and python versions above 3.9 and above, reverted the version and used wsl to run redis locally
- Opened html front and saw the services working as intended
- Used multistage docker to containerize the application, didnt feel a need to containzer frontend as it was simply an html file
- Used official redis docker file
- Implemented docker-compose.yml to run all 3 containers
- Noticed some of the env were hardcoded in worker.py, so used env constants to overide based on current environmen.
- Added env values in the worker service section
- Typed docker-compose up and observed all 3 containers working well and emitting 200 status
- Implemented 4 github action workflows to split responsibilities
- 1. frontend-tf.yml - to spin up aws s3 and cloudfront resources (workflow_dispatch)
  2. frontend-deploy.yml- to push the html file into the mentioned s3 and making it publicly accessable and invalidation cdn cache
  3. backend-tf.yml - to spin up vpc, ecs, tasks, iam permissions,and cloudwatch metrics
  4. backend-deploy.yml- to checkout, build docker images and test using trivy vulnerability scanner, to upload to aws ecr and to push to ecs
- Learnt that ElastiCache is preffered for deploying Redis into aws, used only 2 tasks, worker and backend
- Added cloud watch metrics and cpu alerts
- Uploaded basic diagram into github
- Thank you!

```

