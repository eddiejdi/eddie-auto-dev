import com.atlassian.jira.component.ComponentManager;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.CustomFieldType;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextFieldType;
import com.atlassian.jira.user.UserManager;
import com.atlassian.plugin.spring.scanner.annotation.ComponentScope;
import com.atlassian.plugin.spring.scanner.annotation.Inject;
import com.atlassian.plugin.spring.scanner.annotation.Plugin;
import org.springframework.stereotype.Service;

@Service
@ComponentScope("singleton")
@Plugin("com.example.javaagent.jira")
public class JavaAgent {

    @Inject
    private IssueManager issueManager;

    @Inject
    private FieldManager fieldManager;

    @Inject
    private CustomFieldManager customFieldManager;

    @Inject
    private UserManager userManager;

    public void trackActivity(String issueKey, String activity) {
        try {
            Issue issue = issueManager.getIssueObject(issueKey);
            if (issue != null) {
                TextFieldType descriptionField = fieldManager.getFieldByName("Description");
                if (descriptionField != null) {
                    String currentDescription = issue.getDescription();
                    String newDescription = currentDescription + "\n" + activity;
                    issue.setDescription(newDescription);
                    issueManager.updateIssue(issue, false);
                }
            } else {
                System.out.println("Issue not found: " + issueKey);
            }
        } catch (Exception e) {
            System.err.println("Error tracking activity for issue " + issueKey + ": " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        JavaAgent agent = new JavaAgent();
        agent.trackActivity("JRA-123", "User logged in");
    }
}