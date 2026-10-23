package evaluator.harness;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import java.io.File;
import java.io.FileOutputStream;
import java.io.PrintStream;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;

public final class HarnessActivity extends Activity {
  private static final String TAG = "BenchmarkObserver";

  @Override
  protected void onCreate(Bundle state) {
    super.onCreate(state);
    String probeClass = getIntent().getStringExtra("probeClass");
    new Thread(() -> runProbe(probeClass), "benchmark-observer").start();
  }

  private void runProbe(String probeClass) {
    File observations = new File(getFilesDir(), "runtime.jsonl");
    File status = new File(getFilesDir(), "runtime.status");
    try (PrintStream output = new PrintStream(new FileOutputStream(observations, false), true, StandardCharsets.UTF_8)) {
      PrintStream original = System.out;
      System.setOut(output);
      try {
        Class<?> probe = Class.forName(probeClass);
        try {
          Method installApplication = probe.getDeclaredMethod("installHarnessApplication", android.app.Application.class);
          installApplication.invoke(null, getApplication());
        } catch (NoSuchMethodException ignored) {
          // Most probes have no Android context dependency.
        }
        Method main = probe.getDeclaredMethod("main");
        main.invoke(null);
      } finally {
        output.flush();
        System.setOut(original);
      }
      write(status, "ok\n");
      Log.i(TAG, "COMPLETE " + probeClass);
    } catch (Throwable error) {
      try {
        write(status, "error\n" + Log.getStackTraceString(error));
      } catch (Throwable ignored) {
        Log.e(TAG, "Could not persist harness failure", ignored);
      }
      Log.e(TAG, "FAILED " + probeClass, error);
    } finally {
      finish();
    }
  }

  private static void write(File target, String value) throws Exception {
    try (FileOutputStream output = new FileOutputStream(target, false)) {
      output.write(value.getBytes(StandardCharsets.UTF_8));
    }
  }
}
