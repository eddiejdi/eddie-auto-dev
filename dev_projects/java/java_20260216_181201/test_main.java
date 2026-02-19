import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.issue.fields.TextField;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.jira.service.ServiceContextFactory;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class JavaAgentTest {

    @Autowired
    private Jira jira;

    @Autowired
    private FieldManager fieldManager;

    @Autowired
    private ProjectManager projectManager;

    @BeforeEach
    public void setUp() {
        // Setup code if needed
    }

    @Test
    public void testLogActivitySuccess() throws Exception {
        JavaAgent agent = new JavaAgent();
        String issueId = "ABC-123";
        String activity = "User logged in";

        agent.logActivity(issueId, activity);

        Issue updatedIssue = jira.getIssueObject(issueId);
        TextField descriptionField = (TextField) fieldManager.getFieldByName("Description");
        if (descriptionField != null) {
            String currentDescription = updatedIssue.getDescription();
            String expectedDescription = currentDescription + "\n" + activity;
            assert expectedDescription.equals(currentDescription) : "Description should be updated correctly.";
        } else {
            System.out.println("Description field not found.");
        }
    }

    @Test
    public void testLogActivityError() throws Exception {
        JavaAgent agent = new JavaAgent();
        String issueId = "ABC-123";
        String activity = "";

        agent.logActivity(issueId, activity);

        Issue updatedIssue = jira.getIssueObject(issueId);
        TextField descriptionField = (TextField) fieldManager.getFieldByName("Description");
        if (descriptionField != null) {
            String currentDescription = updatedIssue.getDescription();
            assert expectedDescription.equals(currentDescription) : "Description should be updated correctly.";
        } else {
            System.out.println("Description field not found.");
        }
    }

    @Test
    public void testLogActivityEdgeCase() throws Exception {
        JavaAgent agent = new JavaAgent();
        String issueId = "ABC-123";
        String activity = null;

        agent.logActivity(issueId, activity);

        Issue updatedIssue = jira.getIssueObject(issueId);
        TextField descriptionField = (TextField) fieldManager.getFieldByName("Description");
        if (descriptionField != null) {
            String currentDescription = updatedIssue.getDescription();
            assert expectedDescription.equals(currentDescription) : "Description should be updated correctly.";
        } else {
            System.out.println("Description field not found.");
        }
    }
}