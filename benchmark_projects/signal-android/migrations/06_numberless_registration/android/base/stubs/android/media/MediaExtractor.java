package android.media;
import java.io.IOException;
public class MediaExtractor {
  public void setDataSource(MediaDataSource source) throws IOException {}
  public int getTrackCount() { return 1; }
  public MediaFormat getTrackFormat(int index) { return new MediaFormat(); }
  public void release() {}
}
