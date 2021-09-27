from flask import Flask, render_template, request
import subprocess

app = Flask(__name__)

@app.route("/")
def start():
    return render_template("home.html")

@app.route("/about.html")
def about():
    return render_template("about.html")

@app.route("/home.html")
def home():
    return render_template("home.html")

@app.route("/contact.html")
def contact():
    return render_template("contact.html")

@app.route("/faq.html")
def faq():
    return render_template("faq.html")

@app.route("/direct.html")
def direct():
    return render_template("direct.html")

@app.route("/onprem.html")
def onprem():
    return render_template("onprem.html")

@app.route("/proxy.html")
def proxy():
    return render_template("proxy.html")

@app.route("/slr.html")
def slr():
    return render_template("slr.html")

@app.route('/register', methods=['GET', 'POST'])
def run_script_direct():
    file = request.form.get("direct")
    print(file)
    result = subprocess.check_output("python ez_register_direct.py " + "~/"+file, shell=True, stderr=subprocess.STDOUT)
    print(result)
    result = result.decode("utf-8")
    return render_template("direct.html", result=result)

@app.route('/register', methods=['GET', 'POST'])
def run_script_onprem():
    file = request.form.get("onprem")
    print(file)
    result = subprocess.check_output("python ez_register_onprem.py " + "~/"+file, shell=True, stderr=subprocess.STDOUT)
    print(result)
    result = result.decode("utf-8")
    return render_template("onprem.html", result=result)

@app.route('/register', methods=['GET', 'POST'])
def run_script_proxy():
    file = request.form.get("proxy")
    print(file)
    result = subprocess.check_output("python ez_register_proxy.py " + "~/"+file, shell=True, stderr=subprocess.STDOUT)
    print(result)
    result = result.decode("utf-8")
    return render_template("proxy.html", result=result)

@app.route('/register', methods=['GET', 'POST'])
def run_script_slr():
    file = request.form.get("slr")
    print(file)
    result = subprocess.check_output("python ez_register_slr.py " + "~/"+file, shell=True, stderr=subprocess.STDOUT)
    print(result)
    result = result.decode("utf-8")
    return render_template("slr.html", result=result)
