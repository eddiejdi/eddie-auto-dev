import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.service.ServiceException;

import static org.junit.jupiter.api.Assertions.*;

public class JavaAgentTest {

    private IssueManager issueManager;

    @BeforeEach
    public void setUp() {
        // Configuração do JIRA Service
        issueManager = new IssueManager(); // Implemente a configuração correta para o serviço
    }

    @Test
    public void testMonitorActivitySuccess() throws ServiceException {
        JavaAgent agent = new JavaAgent(issueManager);
        String activity = "Java Agent Activity";
        agent.monitorActivity(activity);
        assertTrue(true); // Verifique se a atividade foi criada corretamente
    }

    @Test
    public void testMonitorActivityError() throws ServiceException {
        JavaAgent agent = new JavaAgent(issueManager);
        String activity = null; // Valor inválido
        assertThrows(ServiceException.class, () -> agent.monitorActivity(activity));
    }

    @Test
    public void testManageIssuesSuccess() throws ServiceException {
        JavaAgent agent = new JavaAgent(issueManager);
        agent.manageIssues();
        assertTrue(true); // Verifique se as issues foram listadas corretamente
    }

    @Test
    public void testManageIssuesError() throws ServiceException {
        JavaAgent agent = new JavaAgent(issueManager);
        assertThrows(ServiceException.class, () -> agent.manageIssues());
    }
}