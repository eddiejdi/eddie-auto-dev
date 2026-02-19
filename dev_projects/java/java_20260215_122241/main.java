import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.plugin.spring.scanner.annotation.ComponentScanner;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@ComponentScanner
@Service
public class JavaAgentJiraIntegration {

    @Autowired
    private ProjectManager projectManager;

    @Autowired
    private FieldManager fieldManager;

    public void trackActivity(String issueKey, String activity) {
        try {
            Project project = projectManager.getProjectByKey(issueKey);
            if (project != null) {
                Issue issue = project.getIssueObject(issueKey);
                if (issue != null) {
                    CustomFieldManager customFieldManager = fieldManager;
                    TextField descriptionField = customFieldManager.getFieldByName("Description");
                    if (descriptionField != null) {
                        issue.setDescription(descriptionField.getValue(issue));
                        issue.update();
                        System.out.println("Activity tracked: " + activity);
                    } else {
                        System.err.println("Description field not found for project: " + project.getKey());
                    }
                } else {
                    System.err.println("Issue not found with key: " + issueKey);
                }
            } else {
                System.err.println("Project not found with key: " + issueKey);
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        JavaAgentJiraIntegration integration = new JavaAgentJiraIntegration();
        integration.trackActivity("PROJ-123", "This is a test activity.");
    }
}