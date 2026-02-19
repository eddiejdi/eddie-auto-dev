import com.atlassian.jira.component.ComponentAccessor;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.security.SecurityLevelManager;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.jira.user.UserManager;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class JavaAgent {

    private static final Logger logger = LoggerFactory.getLogger(JavaAgent.class);

    public void trackActivity(String issueKey, String activity) {
        try {
            IssueManager issueManager = ComponentAccessor.getIssueManager();
            FieldManager fieldManager = ComponentAccessor.getFieldManager();
            SecurityLevelManager securityLevelManager = ComponentAccessor.getSecurityLevelManager();
            ProjectManager projectManager = ComponentAccessor.getProjectManager();
            UserManager userManager = ComponentAccessor.getUserManager();

            // Retrieve the issue by key
            com.atlassian.jira.issue.Issue issue = issueManager.getIssue(issueKey);

            if (issue == null) {
                logger.error("Issue not found: {}", issueKey);
                return;
            }

            // Update the issue's custom field with activity information
            CustomFieldManager customFieldManager = ComponentAccessor.getCustomFieldManager();
            com.atlassian.jira.issue.fields.CustomField customField = customFieldManager.getFieldByName("Activity");

            if (customField == null) {
                logger.error("Activity field not found");
                return;
            }

            // Set the activity value
            issue.setCustomFieldValue(customField, activity);

            // Save the updated issue
            issueManager.updateIssue(issue);
        } catch (Exception e) {
            logger.error("Error tracking activity", e);
        }
    }

    public static void main(String[] args) {
        JavaAgent agent = new JavaAgent();
        agent.trackActivity("ABC-123", "Updated by Java Agent");
    }
}