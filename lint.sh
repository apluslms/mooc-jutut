#!/bin/bash

docker build -f .github/workflows/Dockerfile -q . -t prospector
docker run -v /u/88/toivonj15/unix/projects/mooc-jutut:/app -w /app prospector sh -c 'prospector'
docker rm $(docker stop $(docker ps -a -q --filter ancestor=prospector --format="{{.ID}}"))