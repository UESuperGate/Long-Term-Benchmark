package org.signal.benchmark.waveform;

import android.app.Activity;
import android.os.Bundle;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import org.json.JSONException;
import org.json.JSONObject;

public final class VoiceWaveformActivity extends Activity {
  private WaveformPageOwner owner;
  private TextView status;

  @Override public void onCreate(Bundle state) {
    super.onCreate(state);
    owner = new WaveformPageOwner(this);
    LinearLayout page = new LinearLayout(this);
    page.setOrientation(LinearLayout.VERTICAL);
    page.setPadding(32, 32, 32, 32);
    TextView title = new TextView(this);
    title.setText("Voice note waveform pipeline");
    title.setTextSize(24);
    status = new TextView(this);
    status.setText("Ready");
    Button generate = new Button(this);
    generate.setText("Generate waveform");
    generate.setOnClickListener(view -> {
      try {
        owner.generateWaveform(fullScaleSamples(), 2_000_000L);
        syncSurface();
      } catch (JSONException error) {
        status.setText(error.getMessage());
      }
    });
    Button upload = new Button(this);
    upload.setText("Prepare upload");
    upload.setOnClickListener(view -> {
      try {
        owner.startUploadGraph();
        owner.releaseHeldWaveform(fullScaleSamples(), 2_000_000L);
        syncSurface();
      } catch (JSONException error) {
        status.setText(error.getMessage());
      }
    });
    page.addView(title);
    page.addView(generate);
    page.addView(upload);
    page.addView(status);
    setContentView(page);
  }

  public void prepare(JSONObject given) throws JSONException {
    owner.mount(given);
    syncSurface();
  }

  public WaveformPageOwner owner() { return owner; }

  public String pageOwnerId() { return "VoiceWaveformActivity:" + System.identityHashCode(this); }

  public void syncSurface() throws JSONException {
    status.setText(owner.snapshot().optJSONObject("state").toString());
  }

  private static int[] fullScaleSamples() {
    int[] samples = new int[100];
    java.util.Arrays.fill(samples, 32767);
    return samples;
  }
}
