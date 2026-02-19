import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.jira.service.ServiceContextFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class JavaAgent {

    @Autowired
    private Jira jira;

    @Autowired
    private FieldManager fieldManager;

    @Autowired
    private ProjectManager projectManager;

    public void logActivity(String issueId, String activity) {
        try {
            JiraServiceContext serviceContext = ServiceContextFactory.getJiraServiceContext();
            Issue issue = jira.getIssueObject(issueId);
            CustomFieldManager customFieldManager = fieldManager.getInstance();

            TextField descriptionField = (TextField) customFieldManager.getFieldByName("Description");
            if (descriptionField != null) {
                String currentDescription = issue.getDescription();
                String updatedDescription = currentDescription + "\n" + activity;
                issue.setDescription(updatedDescription);
                jira.updateIssue(serviceContext, issue);
            } else {
                System.out.println("Description field not found.");
            }
        } catch (Exception e) {
            System.err.println("Error logging activity: " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        JavaAgent agent = new JavaAgent();
        agent.logActivity("ABC-123", "User logged in");
    }
}