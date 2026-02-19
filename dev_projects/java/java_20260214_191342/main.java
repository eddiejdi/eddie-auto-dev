import com.atlassian.jira.ComponentManager;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomField;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.issue.fields.types.TextFieldType;
import com.atlassian.jira.user.User;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class JavaAgent {

    @Autowired
    private FieldManager fieldManager;

    @Autowired
    private ComponentManager componentManager;

    public void logActivity(String issueKey, String activity) {
        try {
            Issue issue = componentManager.getIssueObject(issueKey);
            CustomField customField = fieldManager.getFieldByName("Customfield_10100"); // Replace with your custom field ID
            if (customField != null && customField.getType() instanceof TextFieldType) {
                TextField textField = (TextField) customField;
                issue.update(fields -> fields.put(textField.getName(), activity));
            }
        } catch (Exception e) {
            System.err.println("Error logging activity: " + e.getMessage());
        }
    }

    public void monitorActivity(String issueKey, String expectedActivity) {
        try {
            Issue issue = componentManager.getIssueObject(issueKey);
            CustomField customField = fieldManager.getFieldByName("Customfield_10100"); // Replace with your custom field ID
            if (customField != null && customField.getType() instanceof TextFieldType) {
                TextField textField = (TextField) customField;
                String currentActivity = issue.getFields().get(textField.getName()).getValue();
                if (!currentActivity.equals(expectedActivity)) {
                    System.err.println("Activity mismatch: " + currentActivity + " expected: " + expectedActivity);
                }
            }
        } catch (Exception e) {
            System.err.println("Error monitoring activity: " + e.getMessage());
        }
    }

    public void alertProblems(String issueKey, String problemDescription) {
        try {
            Issue issue = componentManager.getIssueObject(issueKey);
            CustomField customField = fieldManager.getFieldByName("Customfield_10100"); // Replace with your custom field ID
            if (customField != null && customField.getType() instanceof TextFieldType) {
                TextField textField = (TextField) customField;
                issue.update(fields -> fields.put(textField.getName(), problemDescription));
            }
        } catch (Exception e) {
            System.err.println("Error alerting problems: " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        JavaAgent agent = new JavaAgent();
        agent.logActivity("JRA-100", "Starting development");
        agent.monitorActivity("JRA-100", "Starting development");
        agent.alertProblems("JRA-100", "System is down");
    }
}