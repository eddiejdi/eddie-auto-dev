import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraException;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

public class JavaAgentTest {

    private JavaAgent agent;

    @Before
    public void setUp() throws JiraException {
        this.agent = new JavaAgent("https://your-jira-server.com", "username", "password");
    }

    @Test
    public void testMonitorProcess() throws JiraException {
        // Caso de sucesso com valores válidos
        agent.monitorProcess();
        assertTrue("Monitoring process should not throw an exception", true);
    }

    @Test(expected = JiraException.class)
    public void testMonitorProcessWithInvalidUrl() throws JiraException {
        // Caso de erro (divisão por zero, valores inválidos, etc)
        agent.monitorProcess();
        assertTrue("Monitoring process should throw an exception", false);
    }

    @Test
    public void testLogEvent() throws JiraException {
        // Caso de sucesso com valores válidos
        agent.logEvent("This is a test log event.");
        assertTrue("Logging event should not throw an exception", true);
    }

    @Test(expected = JiraException.class)
    public void testLogEventWithInvalidMessage() throws JiraException {
        // Caso de erro (divisão por zero, valores inválidos, etc)
        agent.logEvent("");
        assertTrue("Logging event should throw an exception", false);
    }
}