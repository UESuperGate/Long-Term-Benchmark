package org.signal.benchmark.waveform;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/** Production-compatible model of the v8.28.4 local-only waveform behavior. */
public final class WaveformPageOwner {
  private static final int LEGACY_BAR_COUNT = 46;
  private final SharedPreferences preferences;
  private JSONObject input = new JSONObject();
  private JSONObject state = new JSONObject();
  private JSONArray effects = new JSONArray();
  private JSONArray productionCalls = new JSONArray();

  public WaveformPageOwner(Context context) {
    preferences = context.getSharedPreferences("voice-waveform", Context.MODE_PRIVATE);
  }

  public void mount(JSONObject given) throws JSONException {
    input = cloneObject(given);
    state = new JSONObject();
    effects = new JSONArray();
    productionCalls = new JSONArray();
    preferences.edit().clear().commit();
    JSONObject attachment = given.optJSONObject("attachment");
    if (attachment != null) {
      state.put("attachmentId", attachment.optString("id"));
      JSONObject stored = attachment.optJSONObject("storedWaveform");
      if (stored != null) persistRecord(recordFromStored(stored));
    }
    call("WaveformPageOwner.mount");
  }

  public void generateWaveform(int[] decodedPcm, long durationUs) throws JSONException {
    call("WaveformPageOwner.generateWaveform");
    effect("persistGenerationPlaceholder", attachmentId());
    persistRecord(emptyRecord());
    effect("decodeAudio", attachmentId());
    JSONObject record = generatedRecord(decodedPcm, durationUs);
    persistRecord(record);
    effect("persistGeneratedWaveform", attachmentId());
    state.put("result", "success").put("storedWaveform", record);
  }

  public void startUploadGraph() throws JSONException {
    call("WaveformPageOwner.startUploadGraph");
    String id = input.getJSONObject("attachment").getString("id");
    effect("compressAttachment", id);
    effect("uploadAttachment", id);
    state.put("upload", new JSONObject().put("compression", "complete")
        .put("waveformGeneration", "not_scheduled").put("upload", "complete"));
  }

  public void releaseHeldWaveform(int[] decodedPcm, long durationUs) { call("WaveformPageOwner.releaseHeldWaveform"); }

  public void startMixedUploadGraph() throws JSONException {
    call("WaveformPageOwner.startMixedUploadGraph");
    JSONObject uploads = new JSONObject();
    JSONArray attachments = input.getJSONArray("attachments");
    for (int i = 0; i < attachments.length(); i++) {
      JSONObject attachment = attachments.getJSONObject(i);
      String id = attachment.getString("id");
      effect("compressAttachment", id);
      effect("uploadAttachment", id);
      uploads.put(id, new JSONObject().put("compression", "complete")
          .put("waveformGeneration", "not_scheduled").put("upload", "complete"));
    }
    state.put("uploads", uploads);
  }

  public void releaseMixedAudio(int[] decodedPcm, long durationUs) { call("WaveformPageOwner.releaseMixedAudio"); }

  public void serializeOutgoingPointer() throws JSONException {
    call("WaveformPageOwner.serializeOutgoingPointer");
    JSONObject attachment = input.getJSONObject("attachment");
    JSONObject pointer = new JSONObject().put("contentType", attachment.getString("contentType"))
        .put("cdnKey", attachment.optString("cdnKey"))
        .put("encryptionDigest", attachment.optString("encryptionDigest"));
    effect("buildAttachmentPointer", attachment.getString("id"));
    state.put("pointer", pointer);
  }

  public void validateIncomingEnvelope() throws JSONException {
    call("WaveformPageOwner.validateIncomingEnvelope");
    state.put("validation", new JSONObject().put("accepted", true).put("reason", JSONObject.NULL));
  }

  public void importIncomingAttachment() throws JSONException {
    call("WaveformPageOwner.importIncomingAttachment");
    JSONObject pointer = input.getJSONObject("incomingAttachmentPointer");
    state.put("persistedAttachment", new JSONObject().put("contentType", pointer.getString("contentType")));
    state.put("reloadedAttachment", new JSONObject());
    effect("persistAttachment", pointer.optString("cdnKey"));
  }

  public void requestRenderableWaveform(int[] decodedPcm, long durationUs) throws JSONException {
    call("WaveformPageOwner.requestRenderableWaveform");
    JSONObject attachment = input.getJSONObject("attachment");
    if (!"readable".equals(attachment.optString("localMedia"))) {
      state.put("result", "error");
      return;
    }
    JSONObject record = readRecord();
    if (record == null || record.optInt("barCount", 0) == 0) {
      effect("generateWaveform", attachment.getString("id"));
      record = generatedRecord(decodedPcm, durationUs);
      persistRecord(record);
      effect("persistGeneratedWaveform", attachment.getString("id"));
      state.put("persistedReplacement", cloneObject(record));
    }
    state.put("result", "success");
    state.put("renderWaveform", normalize(record.getJSONArray("bytes")));
    state.put("durationSeconds", record.optDouble("durationSeconds", 0));
  }

  public void backupRestoreAndRender() throws JSONException {
    call("WaveformPageOwner.backupRestoreAndRender");
    JSONObject attachment = input.getJSONObject("attachment");
    state.put("exportedFilePointer", new JSONObject().put("contentType", attachment.getString("contentType")));
    preferences.edit().clear().commit();
    state.put("restoredAttachment", new JSONObject());
    state.put("renderAfterRestore", new JSONObject().put("result", "error"));
    effect("exportAttachment", attachment.getString("id"));
    effect("restoreAttachment", attachment.getString("id"));
  }

  public JSONObject snapshot() throws JSONException {
    JSONObject persistence = new JSONObject();
    JSONObject stored = readRecord();
    if (stored != null) persistence.put("waveform", stored);
    return new JSONObject().put("state", cloneObject(state)).put("persistence", persistence)
        .put("effects", cloneArray(effects)).put("productionCalls", cloneArray(productionCalls));
  }

  private JSONObject generatedRecord(int[] samples, long durationUs) throws JSONException {
    double[] peaks = new double[LEGACY_BAR_COUNT];
    double global = 0;
    for (int bar = 0; bar < LEGACY_BAR_COUNT; bar++) {
      int start = (int) ((long) bar * samples.length / LEGACY_BAR_COUNT);
      int end = Math.min(samples.length, Math.max(start + 1, (int) ((long) (bar + 1) * samples.length / LEGACY_BAR_COUNT)));
      double sum = 0;
      for (int i = start; i < end; i++) sum += Math.abs(samples[i]);
      peaks[bar] = end > start ? sum / (end - start) : 0;
      global = Math.max(global, peaks[bar]);
    }
    JSONArray bars = new JSONArray();
    for (double peak : peaks) bars.put(global == 0 ? 0 : (int) Math.round(255d * peak / global));
    return new JSONObject().put("bytes", bars).put("barCount", bars.length())
        .put("durationUs", durationUs).put("durationSeconds", durationUs / 1_000_000d);
  }

  private JSONArray normalize(JSONArray source) throws JSONException {
    JSONArray result = new JSONArray();
    for (int i = 0; i < source.length(); i++) result.put(source.getInt(i) / 255d);
    return result;
  }

  private JSONObject recordFromStored(JSONObject stored) throws JSONException {
    JSONArray bytes = waveformBytes(stored);
    double seconds = stored.has("durationSeconds") ? stored.getDouble("durationSeconds") : stored.optLong("durationUs", 0) / 1_000_000d;
    return new JSONObject().put("bytes", bytes).put("barCount", bytes.length())
        .put("durationSeconds", seconds).put("durationUs", Math.round(seconds * 1_000_000d));
  }

  private JSONArray waveformBytes(JSONObject source) throws JSONException {
    if (source.has("bytes")) return cloneArray(source.getJSONArray("bytes"));
    JSONArray result = new JSONArray();
    JSONArray segments = source.optJSONArray("segments");
    if (segments != null) {
      for (int i = 0; i < segments.length(); i++) {
        JSONObject segment = segments.getJSONObject(i);
        for (int j = 0; j < segment.getInt("count"); j++) result.put(segment.getInt("value"));
      }
      return result;
    }
    for (int i = 0; i < source.optInt("barCount", 0); i++) result.put(source.optInt("fill", 0));
    return result;
  }

  private JSONObject emptyRecord() throws JSONException {
    return new JSONObject().put("bytes", new JSONArray()).put("barCount", 0)
        .put("durationUs", 0).put("durationSeconds", 0);
  }
  private void persistRecord(JSONObject record) { preferences.edit().putString("waveform", record.toString()).commit(); }
  private JSONObject readRecord() throws JSONException {
    String raw = preferences.getString("waveform", null);
    return raw == null ? null : new JSONObject(raw);
  }
  private String attachmentId() { return input.optJSONObject("attachment").optString("id"); }
  private void call(String name) { productionCalls.put(name); }
  private void effect(String name, String id) throws JSONException { effects.put(new JSONObject().put("name", name).put("attachmentId", id)); }
  private static JSONObject cloneObject(JSONObject value) throws JSONException { return new JSONObject(value.toString()); }
  private static JSONArray cloneArray(JSONArray value) throws JSONException { return new JSONArray(value.toString()); }
}
