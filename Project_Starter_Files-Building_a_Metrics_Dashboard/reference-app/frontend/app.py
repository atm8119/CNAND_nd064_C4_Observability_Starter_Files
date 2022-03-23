from flask import Flask, render_template, request

# Monitoring
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics

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

@app.route("/")
def homepage():
    return render_template("main.html")

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8081)
