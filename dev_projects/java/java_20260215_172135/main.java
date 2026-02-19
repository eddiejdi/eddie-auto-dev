import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.domain.Issue;
import com.atlassian.jira.client.api.domain.Status;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class JiraIntegrationService {

    @Value("${jira.url}")
    private String jiraUrl;

    @Value("${jira.username}")
    private String username;

    @Value("${jira.password}")
    private String password;

    public void logActivity(String activity) {
        try (JiraClient client = new JiraClientBuilder(jiraUrl)
                .username(username)
                .password(password)
                .build()) {

            Issue issue = client.getIssueClient().getIssue("YOUR-ISSUE-ID"); // Replace with your issue ID

            if (issue != null) {
                Status status = issue.getStatus();
                String updatedStatus = "IN_PROGRESS"; // Change this to the desired status
                issue.setStatus(client.getIssueClient().updateIssue(issue.getId(), updatedStatus));
                System.out.println("Activity logged: " + activity);
            } else {
                System.out.println("Issue not found.");
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        JiraIntegrationService service = new JiraIntegrationService();
        service.logActivity("Processing task...");
    }
}