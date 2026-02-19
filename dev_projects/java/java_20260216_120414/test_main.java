import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.jira.service.ServiceContext;
import com.atlassian.jira.user.User;
import com.atlassian.plugin.spring.scanner.annotation.ComponentImport;
import org.junit.Before;
import org.junit.Test;
import org.springframework.beans.factory.annotation.Autowired;

import java.util.List;

public class JavaAgentIntegrationTest {

    @Autowired
    private FieldManager fieldManager;

    @Autowired
    private ProjectManager projectManager;

    @ComponentImport
    private CustomFieldManager customFieldManager;

    private ServiceContext context;
    private User user;
    private Issue issue;
    private TextField statusField;
    private TextField descriptionField;

    @Before
    public void setUp() {
        context = new ServiceContext();
        user = context.getUser();

        // Create a project and an issue
        Project project = projectManager.createProject("SCRUM-13", "Integrar Java Agent com Jira - tracking de atividades");
        issue = projectManager.getIssueObject("SCRUM-13-1");

        statusField = fieldManager.getFieldByName("status");
        descriptionField = fieldManager.getFieldByName("description");
    }

    @Test
    public void testTrackActivitySuccess() {
        String issueKey = "SCRUM-13-1";
        String activity = "New task created";

        trackActivity(issueKey, activity);

        // Check if the status field was updated to 'In Progress'
        List<CustomField> customFields = customFieldManager.getCustomFieldObjectsByName("status");
        for (CustomField customField : customFields) {
            Object value = issue.getCustomFieldValue(customField);
            if (value != null && value.equals("In Progress")) {
                System.out.println("Status field updated successfully");
                return;
            }
        }

        System.err.println("Failed to update status field");
    }

    @Test
    public void testTrackActivityError() {
        String issueKey = "SCRUM-13-1";
        String activity = "";

        trackActivity(issueKey, activity);

        // Check if the description field was updated with the provided activity
        List<CustomField> customFields = customFieldManager.getCustomFieldObjectsByName("description");
        for (CustomField customField : customFields) {
            Object value = issue.getCustomFieldValue(customField);
            if (value != null && value.equals(activity)) {
                System.out.println("Description field updated successfully");
                return;
            }
        }

        System.err.println("Failed to update description field with provided activity");
    }

    // Add more test cases as needed
}