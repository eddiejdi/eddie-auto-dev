import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.service.ServiceException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

public class JavaAgentTest {

    @Mock
    private IssueManager issueManager;

    @InjectMocks
    private JavaAgent javaAgent;

    @BeforeEach
    public void setUp() {
        MockitoAnnotations.openMocks(this);
    }

    @Test
    public void testTrackActivitySuccess() throws ServiceException {
        // Simulando um caso de sucesso com valores válidos
        String issueKey = "JIRA-123";
        String activityDescription = "User logged in";

        javaAgent.trackActivity(issueKey, activityDescription);

        // Verificando se o método foi chamado corretamente
        verify(issueManager).getIssueObject(issueKey);
    }

    @Test
    public void testTrackActivityFailure() throws ServiceException {
        // Simulando um caso de erro (divisão por zero)
        String issueKey = "JIRA-123";
        String activityDescription = "";

        try {
            javaAgent.trackActivity(issueKey, activityDescription);
            fail("Expected an exception to be thrown");
        } catch (ServiceException e) {
            // Verificando se o método foi chamado corretamente
            verify(issueManager).getIssueObject(issueKey);
            assertEquals("Error tracking activity: Division by zero", e.getMessage());
        }
    }

    @Test
    public void testTrackActivityNullArgument() throws ServiceException {
        // Simulando um caso de erro (argumento nulo)
        String issueKey = null;
        String activityDescription = "User logged in";

        try {
            javaAgent.trackActivity(issueKey, activityDescription);
            fail("Expected an exception to be thrown");
        } catch (ServiceException e) {
            // Verificando se o método foi chamado corretamente
            verify(issueManager).getIssueObject(issueKey);
            assertEquals("Error tracking activity: Issue key cannot be null", e.getMessage());
        }
    }

    @Test
    public void testTrackActivityInvalidArgument() throws ServiceException {
        // Simulando um caso de erro (argumento inválido)
        String issueKey = "JIRA-123";
        String activityDescription = "User logged in";

        try {
            javaAgent.trackActivity(issueKey, "");
            fail("Expected an exception to be thrown");
        } catch (ServiceException e) {
            // Verificando se o método foi chamado corretamente
            verify(issueManager).getIssueObject(issueKey);
            assertEquals("Error tracking activity: Activity description cannot be empty", e.getMessage());
        }
    }

    @Test
    public void testTrackActivityEdgeCase() throws ServiceException {
        // Simulando um caso de edge case (valores limite)
        String issueKey = "JIRA-123";
        String activityDescription = "User logged in";

        javaAgent.trackActivity(issueKey, "A" + "B".repeat(99));

        // Verificando se o método foi chamado corretamente
        verify(issueManager).getIssueObject(issueKey);
    }
}