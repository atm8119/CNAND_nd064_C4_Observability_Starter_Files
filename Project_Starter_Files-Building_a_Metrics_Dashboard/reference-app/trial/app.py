import logging
import re
import requests


from flask import Flask, jsonify, render_template

from prometheus_flask_exporter import PrometheusMetrics

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

app = Flask(__name__, template_folder='templates')

# -- Monitoring: Define static Monitoring metrics --
metrics = PrometheusMetrics(app)
metrics.info("app_info", "Application info", version="2.0.0")

# -- Observability: Prep app for tracing -- 
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()
# -- -- Configure Tracer 
trace.set_tracer_provider(
    TracerProvider(
        resource=Resource.create({SERVICE_NAME: "trial-service"})  
    )
)
# -- -- Set Jaeger Exporter --
jaeger_exporter = JaegerExporter(
    # configure agent
    agent_host_name='localhost',
    agent_port=6831,
    # optional: configure also collector
    # collector_endpoint='http://localhost:14268/api/traces?format=jaeger.thrift',
    # username=xxxx, # optional
    # password=xxxx, # optional
    # max_tag_value_length=None # optional
)

# -- -- Create a BatchSpanProcessor and add the exporter to it --
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(jaeger_exporter)
)
# -- -- Initialize Tracer --
tracer = trace.get_tracer(__name__)

## -- Logging: Define logging parameters --
logging.getLogger("").handlers = []
logging.basicConfig(format="%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)

# -- Application Body: Routes and Logic --
@app.route("/")
def homepage():
    return render_template("main.html")


@app.route("/trace")
def trace():
    def remove_tags(text):
        tag = re.compile(r"<[^>]+>")
        return tag.sub("", text)

    with tracer.start_span("get-python-jobs") as span:
        res = requests.get("https://jobs.github.com/positions.json?description=python")
        span.log_kv({"event": "get jobs count", "count": len(res.json())})
        span.set_tag("jobs-count", len(res.json()))

        jobs_info = []
        for result in res.json():
            jobs = {}
            with tracer.start_span("request-site") as site_span:
                logger.info(f"Getting website for {result['company']}")
                try:
                    jobs["description"] = remove_tags(result["description"])
                    jobs["company"] = result["company"]
                    jobs["company_url"] = result["company_url"]
                    jobs["created_at"] = result["created_at"]
                    jobs["how_to_apply"] = result["how_to_apply"]
                    jobs["location"] = result["location"]
                    jobs["title"] = result["title"]
                    jobs["type"] = result["type"]
                    jobs["url"] = result["url"]

                    jobs_info.append(jobs)
                    site_span.set_tag("http.status_code", res.status_code)
                    site_span.set_tag("company-site", result["company"])
                except Exception:
                    logger.error(f"Unable to get site for {result['company']}")
                    site_span.set_tag("http.status_code", res.status_code)
                    site_span.set_tag("company-site", result["company"])

    return jsonify(jobs_info)


if __name__ == "__main__":
    app.run(debug=True,)
