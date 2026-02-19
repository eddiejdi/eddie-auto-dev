import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.User;
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

    public void trackActivity(String issueKey, String activity) {
        try (JiraClient client = new JiraClientBuilder(jiraUrl)
                .username(username)
                .password(password)
                .build()) {

            Issue issue = client.getIssue(issueKey);
            User user = client.getUser(client.getCurrentUser().getName());

            System.out.println("Tracking activity for issue " + issueKey + ": " + activity);

            // Add your logic to track the activity in Jira here
        } catch (Exception e) {
            System.err.println("Error tracking activity: " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        JiraService jiraService = new JiraService();
        jiraService.trackActivity("ABC-123", "User logged in");
    }
}