import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraException;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.fields.CustomFieldManager;
import com.atlassian.jira.issue.fields.FieldManager;
import com.atlassian.jira.user.User;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class JavaAgentTest {

    private JavaAgent agent;
    private Jira jira;

    @BeforeEach
    public void setUp() {
        // Simulação de uma instância de Jira
        jira = new MockJira();
        agent = new JavaAgent(jira);
    }

    @Test
    public void testMonitorarAtividadesSucesso() throws JiraException {
        Project project = jira.getProject("YOUR_PROJECT_KEY");
        FieldManager fieldManager = jira.getFieldManager();
        CustomFieldManager customFieldManager = jira.getCustomFieldManager();

        // Simulação de tarefas com status "In Progress"
        Issue[] issues = new Issue[]{new MockIssue("T123", "In Progress")};

        agent.monitorarAtividades(issues);

        // Verifica se os dados foram impressos corretamente
        verifyOutput();
    }

    @Test
    public void testMonitorarAtividadesErro() throws JiraException {
        Project project = jira.getProject("YOUR_PROJECT_KEY");
        FieldManager fieldManager = jira.getFieldManager();
        CustomFieldManager customFieldManager = jira.getCustomFieldManager();

        // Simulação de tarefas com status "In Progress"
        Issue[] issues = new Issue[]{new MockIssue("T123", "In Progress")};

        try {
            agent.monitorarAtividades(issues);
        } catch (JiraException e) {
            assertEquals("Erro ao monitorar atividades", e.getMessage());
        }
    }

    private void verifyOutput() {
        // Verifica se os dados foram impressos corretamente
        // Implemente a lógica para verificar o output do console
    }
}