import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.service.ServiceContext;
import com.atlassian.jira.web.bean.context.UserSession;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class JavaAgentTest {

    private JavaAgent agent;

    @BeforeEach
    public void setUp() {
        agent = new JavaAgent();
        // Mocking dependencies (Issue, ServiceContext, UserSession)
        // This is a placeholder for actual mocking and setup logic
    }

    @Test
    public void testLogEventSuccess() {
        String eventType = "User Login";
        String eventData = "User logged in as john_doe";

        agent.logEvent(eventType, eventData);

        assertEquals("Logging event: User Login, Data: User logged in as john_doe", System.out.toString());
    }

    @Test
    public void testLogEventError() {
        String eventType = "Invalid Operation";
        String eventData = "";

        assertThrows(IllegalArgumentException.class, () -> agent.logEvent(eventType, eventData));
    }

    // Add more test cases for monitorActivity and reportStatus methods
}