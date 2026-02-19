import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.auth.BasicHttpAuthenticationHandler;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class JiraService {

    @Value("${jira.url}")
    private String jiraUrl;

    @Value("${jira.username}")
    private String username;

    @Value("${jira.password}")
    private String password;

    public void logActivity(String activity) {
        try (JiraClient client = new JiraClientBuilder(jiraUrl)
                .setAuthenticationHandler(new BasicHttpAuthenticationHandler(username, password))
                .build()) {

            // Implement logic to log the activity
            System.out.println("Logging activity: " + activity);
        } catch (Exception e) {
            System.err.println("Error logging activity: " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        JiraService jiraService = new JiraService();
        jiraService.logActivity("New feature implemented");
    }
}