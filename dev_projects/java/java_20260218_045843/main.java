import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.component.ComponentManager;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.LabelManager;
import com.atlassian.jira.issue.fields.status.StatusManager;
import com.atlassian.jira.user.User;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class JavaAgent {

    @Autowired
    private Jira jira;

    public void trackActivity(String issueKey, String activity) {
        try {
            // Get the issue object
            Issue issue = jira.getIssueObject(issueKey);

            // Get the custom field manager to access custom fields
            CustomFieldManager customFieldManager = ComponentManager.getInstance().getCustomFieldManager();

            // Get the label manager to access labels
            LabelManager labelManager = ComponentManager.getInstance().getLabelManager();

            // Get the status manager to access statuses
            StatusManager statusManager = ComponentManager.getInstance().getStatusManager();

            // Add a comment to the issue
            jira.addComment(issue, "Activity: " + activity);

            // Update the issue with a new label
            labelManager.addLabelToIssue(issue.getKey(), "activity", false);

            // Update the issue with a new status
            statusManager.updateStatus(issue.getKey(), statusManager.getStatus("In Progress"));

        } catch (Exception e) {
            System.err.println("Error tracking activity: " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        JavaAgent agent = new JavaAgent();
        agent.trackActivity("JIRA-123", "New feature implemented");
    }
}