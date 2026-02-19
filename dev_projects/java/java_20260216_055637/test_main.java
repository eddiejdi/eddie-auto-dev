import com.atlassian.jira.client.api.JiraClient;
import com.atlassian.jira.client.api.JiraClientBuilder;
import com.atlassian.jira.client.api.RestException;

public class JavaAgentTest {

    private JavaAgent agent;

    @Before
    public void setUp() {
        String username = "your_username";
        String password = "your_password";
        this.agent = new JavaAgent(username, password);
    }

    @After
    public void tearDown() {
        // Cleanup code if needed
    }

    @Test(expected = RestException.class)
    public void testRegisterEventWithInvalidUsername() throws Exception {
        agent.registerEvent("New task created");
    }

    @Test
    public void testRegisterEventWithValidData() throws Exception {
        String event = "New task created";
        agent.registerEvent(event);
        // Add assertions to verify the event was registered correctly
    }

    @Test(expected = RestException.class)
    public void testMonitorProcessWithInvalidUsername() throws Exception {
        agent.monitorProcess();
    }

    @Test
    public void testMonitorProcessWithValidData() throws Exception {
        String process = "Processing task";
        agent.monitorProcess(process);
        // Add assertions to verify the process was monitored correctly
    }
}