import java.io.*; import java.nio.file.*;
public class Probe { public static void main(String[] a) throws Exception {
  File f = new File(a[0]); File d = f.getParentFile();
  System.out.println("File.canWrite=" + f.canWrite() + " Files.isWritable=" + Files.isWritable(f.toPath()) + " dir.canWrite=" + d.canWrite());
  try (RandomAccessFile r = new RandomAccessFile(f, "rw")) { System.out.println("RAF rw: OK"); } catch (Exception e) { System.out.println("RAF rw: " + e); }
  File t = new File(d, "probe.tmp");
  try (FileOutputStream o = new FileOutputStream(t)) { o.write(1); System.out.println("create in dir: OK"); } catch (Exception e) { System.out.println("create in dir: " + e); }
  t.delete();
  try (RandomAccessFile r = new RandomAccessFile(f, "rw"); java.nio.channels.FileLock l = r.getChannel().tryLock()) { System.out.println("tryLock: " + (l != null ? "acquired" : "null (held elsewhere)")); } catch (Exception e) { System.out.println("tryLock: " + e); }
}}
