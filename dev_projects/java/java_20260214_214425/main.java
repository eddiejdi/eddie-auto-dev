import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.jira.service.ServiceContext;
import com.atlassian.jira.user.User;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class JavaAgent {

    @Autowired
    private FieldManager fieldManager;

    @Autowired
    private ProjectManager projectManager;

    public void trackActivity(Issue issue, User user) {
        try {
            // Get the custom field for tracking activity
            CustomFieldManager customFieldManager = fieldManager;
            TextField trackingField = customFieldManager.getCustomFieldByName("Tracking Field");

            if (trackingField != null) {
                // Set the value of the tracking field
                issue.setCustomFieldValue(trackingField, "Activity tracked by Java Agent");
            } else {
                System.out.println("Tracking field not found");
            }

            // Update the issue in Jira
            projectManager.updateIssue(issue, ServiceContext.current(), null);
        } catch (Exception e) {
            System.err.println("Error tracking activity: " + e.getMessage());
        }
    }
}