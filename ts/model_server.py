"""
File to define the entry point to Model Server
"""

import os
import re
import subprocess
import sys
import tempfile
from builtins import str

import psutil
from ts.version import __version__
from ts.arg_parser import ArgParser


def start():
    """
    This is the entry point for model server
    :return:
    """
    args = ArgParser.ts_parser().parse_args()
    pid_file = os.path.join(tempfile.gettempdir(), ".model_server.pid")
    pid = None
    if os.path.isfile(pid_file):
        with open(pid_file, "r") as f:
            pid = int(f.readline())

    # pylint: disable=too-many-nested-blocks
    if args.version:
        print("TorchServe Version is {}".format(__version__))
        return
    if args.stop:
        if pid is None:
            print("TorchServe is not currently running.")
        else:
            try:
                parent = psutil.Process(pid)
                parent.terminate()
                print("TorchServe has stopped.")
            except (OSError, psutil.Error):
                print("TorchServe already stopped.")
            os.remove(pid_file)
    else:
        if pid is not None:
            try:
                psutil.Process(pid)
                print("TorchServe is already running, please use torchserve --stop to stop TorchServe.")
                sys.exit(1)
            except psutil.Error:
                print("Removing orphan pid file.")
                os.remove(pid_file)
        print(1)
        java_home = os.environ.get("JAVA_HOME")
        java = "java" if not java_home else "{}/bin/java".format(java_home)
        print(2)
        ts_home = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        cmd = [java, "-Dmodel_server_home={}".format(ts_home)]
        if args.log_config:
            log_config = os.path.realpath(args.log_config)
            if not os.path.isfile(log_config):
                print("--log-config file not found: {}".format(log_config))
                sys.exit(1)

            cmd.append("-Dlog4j.configuration=file://{}".format(log_config))
        print(3)
        tmp_dir = os.environ.get("TEMP")
        if tmp_dir:
            if not os.path.isdir(tmp_dir):
                print("Invalid temp directory: {}, please check TEMP environment variable.".format(tmp_dir))
                sys.exit(1)

            cmd.append("-Djava.io.tmpdir={}".format(tmp_dir))
        print(4)
        ts_config = args.ts_config
        ts_conf_file = None
        if ts_config:
            if not os.path.isfile(ts_config):
                print("--ts-config file not found: {}".format(ts_config))
                sys.exit(1)
            ts_conf_file = ts_config
        print(4)
        class_path = \
            ".:{}".format(os.path.join(ts_home, "ts/frontend/*"))
        print(5)
        if ts_conf_file and os.path.isfile(ts_conf_file):
            props = load_properties(ts_conf_file)
            vm_args = props.get("vmargs")
            if vm_args:
                print("Warning: TorchServe is using non-default JVM parameters: {}".format(vm_args))
                arg_list = vm_args.split()
                if args.log_config:
                    for word in arg_list[:]:
                        if word.startswith("-Dlog4j.configuration="):
                            arg_list.remove(word)
                cmd.extend(arg_list)
            plugins = props.get("plugins_path", None)
            if plugins:
                class_path += ":" + plugins + "/*" if "*" not in plugins else ":" + plugins

            if not args.model_store and props.get('model_store'):
                args.model_store = props.get('model_store')
        print(6)
        cmd.append("-cp")
        cmd.append(class_path)
        print(7)
        cmd.append("org.pytorch.serve.ModelServer")
        print(8)
        # model-server.jar command line parameters
        cmd.append("--python")
        cmd.append(sys.executable)
        print(9)
        if ts_conf_file is not None:
            cmd.append("-f")
            cmd.append(ts_conf_file)
        print(10)
        if args.model_store:
            if not os.path.isdir(args.model_store):
                print("--model-store directory not found: {}".format(args.model_store))
                sys.exit(1)

            cmd.append("-s")
            cmd.append(args.model_store)
        else:
            print("Missing mandatory parameter --model-store")
            sys.exit(1)
        print(11)
        if args.no_config_snapshots:
            cmd.append("-ncs")
        print(12)
        if args.models:
            cmd.append("-m")
            cmd.extend(args.models)
            if not args.model_store:
                pattern = re.compile(r"(.+=)?http(s)?://.+", re.IGNORECASE)
                for model_url in args.models:
                    if not pattern.match(model_url) and model_url != "ALL":
                        print("--model-store is required to load model locally.")
                        sys.exit(1)
        print(13)
        try:
            print(cmd)
            process = subprocess.Popen(cmd)
            pid = process.pid
            with open(pid_file, "w") as pf:
                pf.write(str(pid))
            if args.foreground:
                process.wait()
        except OSError as e:
            if e.errno == 2:
                print("java not found, please make sure JAVA_HOME is set properly.")
            else:
                print("start java frontend failed:", sys.exc_info())


def load_properties(file_path):
    """
    Read properties file into map.
    """
    props = {}
    with open(file_path, "rt") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("#"):
                pair = line.split("=", 1)
                if len(pair) > 1:
                    key = pair[0].strip()
                    props[key] = pair[1].strip()

    return props


if __name__ == "__main__":
    start()
