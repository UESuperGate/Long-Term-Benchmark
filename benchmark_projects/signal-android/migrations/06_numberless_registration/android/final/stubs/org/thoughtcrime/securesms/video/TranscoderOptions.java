package org.thoughtcrime.securesms.video;
public final class TranscoderOptions {
  public final long startTimeUs;
  public final long endTimeUs;
  public TranscoderOptions(long startTimeUs, long endTimeUs) { this.startTimeUs = startTimeUs; this.endTimeUs = endTimeUs; }
}
