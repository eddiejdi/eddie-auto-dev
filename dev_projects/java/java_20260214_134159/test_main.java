import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class JavaAgentTest {

    private JavaAgent javaAgent;

    @BeforeEach
    public void setUp() {
        this.javaAgent = new JavaAgent();
    }

    @Test
    public void testCreateIssueWithValidInputs() {
        // Arrange
        JiraClient jiraClient = mock(JiraClient.class);
        IssueType issueType = mock(IssueType.class);
        User reporter = mock(User.class);

        when(jiraClient.getIssueTypeManager().getIssueTypeByName("Bug")).thenReturn(issueType);
        when(jiraClient.getUserManager().getUserByUserName("reporter")).thenReturn(reporter);

        // Act
        Issue newIssue = javaAgent.createIssue(jiraClient);

        // Assert
        assertNotNull(newIssue, "New issue should not be null");
    }

    @Test
    public void testCreateIssueWithInvalidInputs() {
        // Arrange
        JiraClient jiraClient = mock(JiraClient.class);
        IssueType issueType = mock(IssueType.class);
        User reporter = mock(User.class);

        when(jiraClient.getIssueTypeManager().getIssueTypeByName("Bug")).thenReturn(issueType);
        when(jiraClient.getUserManager().getUserByUserName("reporter")).thenReturn(reporter);

        // Act
        try {
            javaAgent.createIssue(jiraClient);
            fail("Expected an exception to be thrown");
        } catch (Exception e) {
            assertEquals("Failed to create issue", e.getMessage());
        }
    }

    @Test
    public void testCreateIssueWithEdgeCases() {
        // Arrange
        JiraClient jiraClient = mock(JiraClient.class);
        IssueType issueType = mock(IssueType.class);
        User reporter = mock(User.class);

        when(jiraClient.getIssueTypeManager().getIssueTypeByName("Bug")).thenReturn(issueType);
        when(jiraClient.getUserManager().getUserByUserName("reporter")).thenReturn(reporter);

        // Act
        try {
            javaAgent.createIssue(jiraClient);
            fail("Expected an exception to be thrown");
        } catch (Exception e) {
            assertEquals("Failed to create issue", e.getMessage());
        }
    }
}