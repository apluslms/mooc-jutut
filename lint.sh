#!/bin/bash

docker build -f .github/workflows/Dockerfile -q . -t prospector
docker run -v ${PWD}:/app -w /app prospector sh -c 'prospector'
docker rm $(docker stop $(docker ps -a -q --filter ancestor=prospector --format="{{.ID}}"))
