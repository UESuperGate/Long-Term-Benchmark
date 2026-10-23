package android.media;
import java.io.IOException;
public abstract class MediaDataSource implements AutoCloseable {
  public abstract int readAt(long position, byte[] buffer, int offset, int size) throws IOException;
  public abstract long getSize() throws IOException;
  public abstract void close() throws IOException;
}
