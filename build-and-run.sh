# get OpenSerp
#docker pull karust/openserp

#docker run -p 127.0.0.1:7000:7000 -it karust/openserp serve -a 0.0.0.0 -p 7000

docker build -f docker/Dockerfile -t conversational-agent-open-api . --no-cache

docker run -it conversational-agent-open-api
