import com.atlassian.jira.component.ComponentAccessor;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.project.ProjectManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import static org.junit.jupiter.api.Assertions.*;

@Service
public class JavaAgentJiraIntegrationTest {

    @Autowired
    private IssueManager issueManager;

    @Autowired
    private CustomFieldManager customFieldManager;

    @Autowired
    private ProjectManager projectManager;

    @BeforeEach
    public void setUp() {
        // Setup code if needed
    }

    @Test
    public void testTrackActivitySuccess() {
        // Test case for successful tracking of activity
        String issueKey = "ABC-123";
        String activity = "User logged in";

        JavaAgentJiraIntegration integrationService = new JavaAgentJiraIntegration();
        integrationService.trackActivity(issueKey, activity);

        // Assert that the comment was added to the issue
        com.atlassian.jira.issue.Issue issue = issueManager.getIssueObject(issueKey);
        assertNotNull(issue.getComments(), "Comment should be added to the issue");
    }

    @Test
    public void testTrackActivityError() {
        // Test case for error tracking of activity (e.g., invalid issue key)
        String issueKey = "XYZ-987"; // Invalid issue key
        String activity = "User logged in";

        JavaAgentJiraIntegration integrationService = new JavaAgentJiraIntegration();
        try {
            integrationService.trackActivity(issueKey, activity);
            fail("Expected an exception to be thrown");
        } catch (Exception e) {
            assertEquals("Error tracking activity: Invalid issue key", e.getMessage());
        }
    }

    @Test
    public void testTrackActivityEdgeCase() {
        // Test case for edge case (empty string as activity)
        String issueKey = "ABC-123";
        String activity = "";

        JavaAgentJiraIntegration integrationService = new JavaAgentJiraIntegration();
        try {
            integrationService.trackActivity(issueKey, activity);
            fail("Expected an exception to be thrown");
        } catch (Exception e) {
            assertEquals("Error tracking activity: Invalid issue key", e.getMessage());
        }
    }
}