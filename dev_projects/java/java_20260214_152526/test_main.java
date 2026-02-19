import com.atlassian.jira.Jira;
import com.atlassian.jira.JiraServiceContext;
import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.service.ServiceException;

public class JavaAgentTest {

    private Jira jiraMock; // Mock of Jira service context

    @Before
    public void setUp() {
        jiraMock = mock(Jira.class);
    }

    @Test
    public void testTrackActivitySuccess() throws ServiceException {
        Issue issue = mock(Issue.class);
        when(jiraMock.getIssue("ABC-123")).thenReturn(issue);

        JavaAgent javaAgent = new JavaAgent(jiraMock);
        String activityDescription = "User logged in";

        javaAgent.trackActivity("ABC-123", activityDescription);

        verify(jiraMock).getIssue("ABC-123");
        verify(jiraMock).logActivity(any(Issue.class), any(String.class));
    }

    @Test(expected = ServiceException.class)
    public void testTrackActivityInvalidKey() throws ServiceException {
        JavaAgent javaAgent = new JavaAgent(jiraMock);
        String invalidKey = "XYZ-987";
        String activityDescription = "User logged in";

        try {
            javaAgent.trackActivity(invalidKey, activityDescription);
        } catch (ServiceException e) {
            // Expected exception
        }
    }

    @Test(expected = ServiceException.class)
    public void testTrackActivityNullIssue() throws ServiceException {
        JavaAgent javaAgent = new JavaAgent(jiraMock);
        String issueKey = "ABC-123";
        String activityDescription = null;

        try {
            javaAgent.trackActivity(issueKey, activityDescription);
        } catch (ServiceException e) {
            // Expected exception
        }
    }

    @Test(expected = ServiceException.class)
    public void testTrackActivityNullContext() throws ServiceException {
        JavaAgent javaAgent = new JavaAgent(null);

        String issueKey = "ABC-123";
        String activityDescription = "User logged in";

        try {
            javaAgent.trackActivity(issueKey, activityDescription);
        } catch (ServiceException e) {
            // Expected exception
        }
    }
}