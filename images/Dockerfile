FROM python:3.13-slim

RUN pip install cfn-check

RUN mkdir /check
RUN mkdir /templates

WORKDIR /check

COPY ./images/entrypoint.sh entrypoint.sh

RUN chmod +x entrypoint.sh

ENTRYPOINT [ "/check/entrypoint.sh" ]
CMD [ "cfn-check" ]