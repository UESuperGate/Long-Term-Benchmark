"""Same original deadline/export with exact-version JVM variant worker."""
from . import task11_android_sdk_leaf_control_v4 as exporter
from . import task11_android_sdk_leaf_worker_v4 as worker


if __name__ == '__main__':
    exporter.install()
    worker.install()
    raise SystemExit(exporter.previous.main())
