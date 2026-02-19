import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.service.ServiceContext;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class JavaAgentJiraIntegration {

    @Autowired
    private IssueManager issueManager;

    public void trackActivity(String issueKey, String activity) {
        ServiceContext context = new ServiceContext();
        try {
            Issue issue = issueManager.getIssue(context, issueKey);
            if (issue != null) {
                // Implement logic to log the activity in Jira
                System.out.println("Tracking activity for issue " + issueKey + ": " + activity);
            } else {
                System.out.println("Issue not found: " + issueKey);
            }
        } catch (Exception e) {
            System.err.println("Error tracking activity: " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        JavaAgentJiraIntegration integration = new JavaAgentJiraIntegration();
        integration.trackActivity("ABC-123", "User logged in");
    }
}