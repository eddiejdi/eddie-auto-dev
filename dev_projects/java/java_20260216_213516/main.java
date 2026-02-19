import com.atlassian.jira.component.ComponentAccessor;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.types.TextCustomFieldType;
import com.atlassian.jira.user.User;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class JavaAgent {

    @Autowired
    private IssueManager issueManager;

    @Autowired
    private FieldManager fieldManager;

    @Autowired
    private CustomFieldManager customFieldManager;

    public void trackActivity(String issueKey, String activity) {
        try {
            User currentUser = ComponentAccessor.getUserManager().getSystemUser();
            issueManager.createComment(issueKey, currentUser, activity);
        } catch (Exception e) {
            System.err.println("Error tracking activity: " + e.getMessage());
        }
    }

    public void createCustomField(String fieldName, String fieldType) {
        try {
            TextCustomFieldType textCustomFieldType = fieldManager.getTextCustomFieldType();
            customFieldManager.createCustomField(fieldName, textCustomFieldType);
        } catch (Exception e) {
            System.err.println("Error creating custom field: " + e.getMessage());
        }
    }

    public void updateIssueStatus(String issueKey, String statusName) {
        try {
            Issue issue = issueManager.getIssueObject(issueKey);
            issue.setStatus(statusName);
            issue.update();
        } catch (Exception e) {
            System.err.println("Error updating issue status: " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        JavaAgent agent = new JavaAgent();

        // Example usage
        agent.trackActivity("JRA-123", "User logged in");
        agent.createCustomField("Notes", "Text");
        agent.updateIssueStatus("JRA-123", "In Progress");
    }
}