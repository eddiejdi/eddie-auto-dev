import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

public class JiraIntegrationServiceTest {

    @Mock
    private IssueManager issueManager;

    @Mock
    private ProjectManager projectManager;

    @InjectMocks
    private JiraIntegrationService service;

    @BeforeEach
    public void setUp() {
        MockitoAnnotations.openMocks(this);
    }

    @Test
    public void testTrackActivitySuccess() {
        // Arrange
        String issueKey = "ABC-123";
        String activityDescription = "User logged in successfully";

        // Act
        service.trackActivity(issueKey, activityDescription);

        // Assert
        Mockito.verify(issueManager).addComment(activityDescription);
    }

    @Test
    public void testTrackActivityFailure() {
        // Arrange
        String issueKey = "ABC-123";
        String activityDescription = "";

        // Act
        service.trackActivity(issueKey, activityDescription);

        // Assert
        Mockito.verify(issueManager).addComment(activityDescription);
    }

    @Test
    public void testTrackProjectActivitySuccess() {
        // Arrange
        String projectId = "JIRA-456";
        String activityDescription = "New feature implemented";

        // Act
        service.trackProjectActivity(projectId, activityDescription);

        // Assert
        Mockito.verify(issueManager).addComment(activityDescription);
    }

    @Test
    public void testTrackProjectActivityFailure() {
        // Arrange
        String projectId = "JIRA-456";
        String activityDescription = "";

        // Act
        service.trackProjectActivity(projectId, activityDescription);

        // Assert
        Mockito.verify(issueManager).addComment(activityDescription);
    }
}