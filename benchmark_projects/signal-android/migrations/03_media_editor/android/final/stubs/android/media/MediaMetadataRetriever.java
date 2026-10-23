package android.media;
public class MediaMetadataRetriever {
  public static final int METADATA_KEY_DURATION = 9;
  public static final int METADATA_KEY_LOCATION = 23;
  public void setDataSource(MediaDataSource source) {}
  public String extractMetadata(int key) { return key == METADATA_KEY_DURATION ? "1000" : null; }
  public void release() {}
}
