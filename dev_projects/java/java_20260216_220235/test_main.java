import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.ProjectManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.NoSuchElementException;

public class JavaAgentIntegrationTest {

    private Jira jira;
    private IssueManager issueManager;
    private ProjectManager projectManager;

    @BeforeEach
    public void setUp() {
        // Initialize Jira service context
        JiraServiceContext jiraServiceContext = new JiraServiceContext();
        jira = jiraServiceContext.getJira();
        issueManager = jiraServiceContext.getIssueManager();
        projectManager = jiraServiceContext.getProjectManager();
    }

    @Test
    public void testCreateIssueSuccess() {
        String projectId = "PROJECT-123";
        String issueTypeKey = "TASK";
        String summary = "New task created by Java Agent Integration";

        try {
            Issue issue = issueManager.createIssue(projectId, issueTypeKey, summary);
            System.out.println("Created issue ID: " + issue.getId());
            // Additional assertions can be added here if needed
        } catch (Exception e) {
            fail("Failed to create issue: " + e.getMessage());
        }
    }

    @Test
    public void testCreateIssueFailure() {
        String projectId = "PROJECT-123";
        String issueTypeKey = "TASK";
        String summary = null; // Null summary should throw an exception

        try {
            Issue issue = issueManager.createIssue(projectId, issueTypeKey, summary);
            fail("Expected an exception to be thrown for a null summary");
        } catch (IllegalArgumentException e) {
            System.out.println("Caught expected IllegalArgumentException: " + e.getMessage());
        }
    }

    // Add more test cases as needed
}