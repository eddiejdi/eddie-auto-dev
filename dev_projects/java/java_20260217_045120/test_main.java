import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

public class JavaAgentJiraIntegratorTest {

    @Mock
    private IssueManager issueManager;

    @Mock
    private ProjectManager projectManager;

    @InjectMocks
    private JavaAgentJiraIntegrator integrator;

    @BeforeEach
    public void setUp() {
        MockitoAnnotations.openMocks(this);
    }

    @Test
    public void testTrackActivitySuccess() {
        String issueKey = "ABC-123";
        String activity = "User logged in";

        try {
            integrator.trackActivity(issueKey, activity);
            // Verificar se o método foi chamado com os valores esperados
            Mockito.verify(issueManager).getIssueObject(issueKey);
        } catch (Exception e) {
            fail("Unexpected exception: " + e.getMessage());
        }
    }

    @Test
    public void testTrackActivityFailure() {
        String issueKey = "ABC-123";
        String activity = null;

        try {
            integrator.trackActivity(issueKey, activity);
            // Verificar se o método foi chamado com os valores esperados
            Mockito.verify(issueManager).getIssueObject(issueKey);
        } catch (Exception e) {
            fail("Unexpected exception: " + e.getMessage());
        }
    }

    @Test
    public void testTrackActivityNullArgument() {
        String issueKey = null;
        String activity = "User logged in";

        try {
            integrator.trackActivity(issueKey, activity);
            // Verificar se o método foi chamado com os valores esperados
            Mockito.verify(issueManager).getIssueObject(issueKey);
        } catch (Exception e) {
            fail("Unexpected exception: " + e.getMessage());
        }
    }

    @Test
    public void testTrackActivityInvalidArgument() {
        String issueKey = "ABC-123";
        String activity = "";

        try {
            integrator.trackActivity(issueKey, activity);
            // Verificar se o método foi chamado com os valores esperados
            Mockito.verify(issueManager).getIssueObject(issueKey);
        } catch (Exception e) {
            fail("Unexpected exception: " + e.getMessage());
        }
    }

    @Test
    public void testTrackActivityProjectNotFound() {
        String issueKey = "ABC-123";
        String activity = "User logged in";

        try {
            // Simulando a situação de projeto não encontrado
            Mockito.when(issueManager.getIssueObject(issueKey)).thenReturn(null);
            integrator.trackActivity(issueKey, activity);
            fail("Expected exception: Project not found");
        } catch (Exception e) {
            // Verificar se o método foi chamado com os valores esperados
            Mockito.verify(issueManager).getIssueObject(issueKey);
            System.out.println("Project not found exception caught: " + e.getMessage());
        }
    }

    @Test
    public void testTrackActivityException() {
        String issueKey = "ABC-123";
        String activity = "User logged in";

        try {
            // Simulando uma exceção no método getIssueObject
            Mockito.when(issueManager.getIssueObject(issueKey)).thenThrow(new Exception("Simulated exception"));
            integrator.trackActivity(issueKey, activity);
            fail("Expected exception: Issue not found");
        } catch (Exception e) {
            // Verificar se o método foi chamado com os valores esperados
            Mockito.verify(issueManager).getIssueObject(issueKey);
            System.out.println("Exception caught: " + e.getMessage());
        }
    }
}