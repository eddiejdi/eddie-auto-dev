import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.security.JiraAuthenticationContext;
import com.atlassian.jira.service.ServiceContextFactory;
import com.atlassian.plugin.spring.scanner.annotation.ComponentScan;
import com.atlassian.plugin.spring.scanner.annotation.Plugin;

import javax.inject.Inject;
import java.util.HashMap;
import java.util.Map;

@Plugin("com.example.javaagent")
@ComponentScan(basePackages = "com.example.javaagent")
public class JavaAgent {

    @Inject
    private Jira jira;

    public void start() {
        // Configuração do Java Agent no servidor
        Map<String, Object> params = new HashMap<>();
        params.put("server", "http://your-jira-server");
        params.put("username", "your-username");
        params.put("password", "your-password");

        try {
            jira.start(params);
            System.out.println("Java Agent started successfully.");
        } catch (Exception e) {
            System.err.println("Failed to start Java Agent: " + e.getMessage());
        }
    }

    public void stop() {
        // Parada do Java Agent
        try {
            jira.stop();
            System.out.println("Java Agent stopped successfully.");
        } catch (Exception e) {
            System.err.println("Failed to stop Java Agent: " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        JavaAgent agent = new JavaAgent();

        // Caso de sucesso com valores válidos
        try {
            agent.start();
            System.out.println("Java Agent started successfully.");
        } catch (Exception e) {
            System.err.println("Failed to start Java Agent: " + e.getMessage());
        }

        // Caso de erro (divisão por zero)
        try {
            agent.stop(0);
        } catch (Exception e) {
            System.out.println("Expected division by zero error.");
        }

        // Edge cases
        try {
            agent.start(null);
        } catch (Exception e) {
            System.err.println("Expected null server URL error.");
        }
    }
}