import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.plugin.spring.scanner.annotation.ComponentImport;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public class JiraIntegrationService {

    @ComponentImport
    private ProjectManager projectManager;

    @ComponentImport
    private FieldManager fieldManager;

    @ComponentImport
    private CustomFieldManager customFieldManager;

    @Autowired
    private Jira jira;

    public void trackActivity(String issueKey, String activity) {
        try {
            Project project = projectManager.getProjectByKey("YOUR_PROJECT_KEY");
            Issue issue = jira.getIssueObject(project.getKey(), issueKey);

            TextField summaryField = fieldManager.getFieldByName("Summary");
            TextField descriptionField = fieldManager.getFieldByName("Description");

            if (summaryField != null && descriptionField != null) {
                String updatedSummary = issue.getCustomFieldValue(summaryField);
                String updatedDescription = issue.getCustomFieldValue(descriptionField);

                updatedSummary += "\n" + activity;
                updatedDescription += "\n" + activity;

                issue.setCustomFieldValue(summaryField, updatedSummary);
                issue.setCustomFieldValue(descriptionField, updatedDescription);

                jira.updateIssue(project.getKey(), issueKey, new JiraServiceContext());
            } else {
                System.out.println("Fields not found for project: " + project.getName() + ", issue: " + issueKey);
            }
        } catch (Exception e) {
            System.err.println("Error tracking activity: " + e.getMessage());
        }
    }

    public static void main(String[] args) {
        JiraIntegrationService service = new JiraIntegrationService();
        service.trackActivity("YOUR_ISSUE_KEY", "New task added");
    }
}