import com.atlassian.jira.component.ComponentAccessor;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.service.ServiceContext;
import com.atlassian.jira.user.User;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class JavaAgent {

    @Autowired
    private FieldManager fieldManager;

    public void trackActivity(String issueKey, String activity) {
        try {
            ServiceContext serviceContext = ComponentAccessor.getComponent(ServiceContext.class);
            Issue issue = fieldManager.getIssueObject(issueKey, serviceContext);

            if (issue != null) {
                User user = ComponentAccessor.getUserManager().getUserByName("your_username");
                TextField customField = fieldManager.getFieldObject("customfield_12345", serviceContext);

                if (customField != null && user != null) {
                    String currentValue = issue.getCustomFieldValue(customField);
                    if (currentValue == null || currentValue.isEmpty()) {
                        issue.setCustomFieldValue(customField, activity);
                    } else {
                        issue.setCustomFieldValue(customField, currentValue + "\n" + activity);
                    }
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        JavaAgent javaAgent = new JavaAgent();
        javaAgent.trackActivity("JRA-123", "This is a test activity.");
    }
}