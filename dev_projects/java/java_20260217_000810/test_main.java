import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.service.ServiceContextFactory;

import org.junit.Before;
import org.junit.Test;
import static org.junit.Assert.*;

public class JavaAgentTest {

    private Jira jira;
    private JiraServiceContext serviceContext;

    @Before
    public void setUp() {
        jira = new Jira();
        serviceContext = ServiceContextFactory.getJiraServiceContext(jira);
    }

    @Test
    public void testMonitorProcessesAndEvents_success() {
        monitorProcessesAndEvents(serviceContext);
        assertEquals("Monitorando processos e eventos...", System.out.toString());
    }

    @Test(expected = ArithmeticException.class)
    public void testMonitorProcessesAndEvents_divisionByZero() {
        monitorProcessesAndEvents(null); // Simula um caso de erro
    }

    @Test
    public void testManageTasksAndProjects_success() {
        manageTasksAndProjects(serviceContext);
        assertEquals("Gerenciando tarefas e projetos...", System.out.toString());
    }

    private static void monitorProcessesAndEvents(JiraServiceContext serviceContext) {
        // Implementação da funcionalidade de monitoramento de processos e eventos
        System.out.println("Monitorando processos e eventos...");
    }

    private static void manageTasksAndProjects(JiraServiceContext serviceContext) {
        // Implementação da funcionalidade de gerenciamento de tarefas e projetos
        System.out.println("Gerenciando tarefas e projetos...");
    }
}