from flask import Flask, render_template, request

# Monitoring
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics

# Tracing
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

app = Flask(__name__)

# -- Monitoring: Define Monitoring metrics
metrics = PrometheusMetrics(app)
#metrics = GunicornPrometheusMetrics(app)
metrics.info("app_info", "Application info", version="1.0.3")
# Sample custom metrics (unused since there are no outgoing requests)
record_requests_by_status = metrics.summary(
        'requests_by_status', 'Request latencies by status',
        labels={'status': lambda: request.status_code()}
)
record_page_visits = metrics.counter(
    'invocation_by_type', 'Number of invocations by type',
    labels={'item_type': lambda: request.view_args['type']}
)

# -- Observability: Prep app for tracing -- 
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()
# -- -- Configure Tracer 
trace.set_tracer_provider(
    TracerProvider(
        resource=Resource.create({SERVICE_NAME: "front-service"})  
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

# -- Application Body: Routes and Logic --
@app.route("/")
def homepage():
    with tracer.start_as_current_span("homepage"):
        return render_template("main.html")

@app.route("/success-response")
def client_error_page():
    return "Planned 200 response", 200

@app.route("/client-error")
def client_error_page():
    return "Planned 400 error", 400

@app.route("/server-error")
def server_error_page():
    return "Planned 500 error", 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8081)
