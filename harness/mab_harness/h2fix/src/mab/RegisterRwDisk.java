package mab;

import org.h2.store.fs.FilePath;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.env.EnvironmentPostProcessor;
import org.springframework.core.env.ConfigurableEnvironment;

/** Registers the "rwdisk:" H2 file system before Spring creates the datasource. */
public class RegisterRwDisk implements EnvironmentPostProcessor {
    @Override
    public void postProcessEnvironment(ConfigurableEnvironment environment, SpringApplication application) {
        FilePath.register(new RwDiskFilePath());
    }
}
