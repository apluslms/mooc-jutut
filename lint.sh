#!/bin/bash

docker build -f .github/workflows/Dockerfile -q . -t prospector
docker run --rm -v ${PWD}:/app -w /app prospector sh -c 'prospector'
