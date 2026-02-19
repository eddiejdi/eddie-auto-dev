import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.jira.service.ServiceContext;
import com.atlassian.jira.user.User;
import com.atlassian.plugin.spring.scanner.annotation.ComponentImport;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class JavaAgentIntegration {

    @Autowired
    private FieldManager fieldManager;

    @Autowired
    private ProjectManager projectManager;

    @ComponentImport
    private CustomFieldManager customFieldManager;

    public void trackActivity(String issueKey, String activity) {
        try {
            ServiceContext context = new ServiceContext();
            User user = context.getUser();

            Issue issue = projectManager.getIssueObject(issueKey);
            TextField statusField = fieldManager.getFieldByName("status");
            if (statusField != null) {
                issue.setCustomFieldValue(statusField, "In Progress");
            }

            TextField descriptionField = fieldManager.getFieldByName("description");
            if (descriptionField != null) {
                issue.setDescription(activity);
            }

            issue.update();
        } catch (Exception e) {
            System.err.println("Error tracking activity: " + e.getMessage());
        }
    }
}