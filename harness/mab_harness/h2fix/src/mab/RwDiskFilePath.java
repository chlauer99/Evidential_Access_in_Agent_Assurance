package mab;

import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;

import org.h2.store.fs.FilePath;
import org.h2.store.fs.disk.FilePathDisk;

/**
 * H2 disk file system ("rwdisk:" prefix) identical to the default one except for canWrite().
 *
 * H2 2.2 decides whether to open a database read-only via java.nio.file.Files.isWritable. Inside
 * restricted Windows containers (AppContainer sandboxes) that call returns false even when the process
 * can open and write the file, so H2 silently opens the database read-only and every HAPI FHIR search
 * (which writes to its search cache) fails. Here canWrite() tests writability by actually opening the
 * file for writing. No other behaviour changes.
 */
public class RwDiskFilePath extends FilePathDisk {
    public static final String SCHEME = "rwdisk";

    @Override
    public String getScheme() {
        return SCHEME;
    }

    @Override
    public FilePathDisk getPath(String path) {
        RwDiskFilePath p = new RwDiskFilePath();
        if (path.startsWith(SCHEME + ":")) {
            path = path.substring(SCHEME.length() + 1);
        }
        p.name = translateFileName(path);
        return p;
    }

    @Override
    public FilePathDisk toRealPath() {
        FilePath real = super.toRealPath();
        RwDiskFilePath p = new RwDiskFilePath();
        p.name = real.name;
        return p;
    }

    @Override
    public boolean canWrite() {
        Path p = Paths.get(name);
        if (!Files.exists(p)) {
            return false;
        }
        try (FileChannel c = FileChannel.open(p, StandardOpenOption.READ, StandardOpenOption.WRITE)) {
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    @Override
    public String toString() {
        return SCHEME + ":" + name;   // keep the prefix so paths derived from this one stay on this provider
    }
}
