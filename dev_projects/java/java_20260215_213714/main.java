import com.atlassian.jira.component.ComponentAccessor;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.project.ProjectManager;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class JavaAgentJiraIntegration {

    @Autowired
    private IssueManager issueManager;

    @Autowired
    private CustomFieldManager customFieldManager;

    @Autowired
    private ProjectManager projectManager;

    public void trackActivity(String issueKey, String activity) {
        try {
            // Retrieve the issue object by key
            com.atlassian.jira.issue.Issue issue = issueManager.getIssueObject(issueKey);

            // Create a new comment on the issue
            com.atlassian.jira.issue.comment.Comment comment = issue.addComment(activity);
            System.out.println("Activity tracked: " + activity);

        } catch (Exception e) {
            System.err.println("Error tracking activity: " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        JavaAgentJiraIntegration integrationService = new JavaAgentJiraIntegration();
        integrationService.trackActivity("ABC-123", "User logged in");
    }
}