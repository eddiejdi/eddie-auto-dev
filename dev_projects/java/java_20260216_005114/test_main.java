import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class JavaAgentJiraIntegrationTest {

    private JiraClient client;

    @BeforeEach
    public void setUp() throws IOException {
        // Configuração do Jira Client
        String jiraUrl = "https://your-jira-instance.com";
        String username = "your-username";
        String password = "your-password";

        client = new JiraClientBuilder(jiraUrl).username(username).password(password).build();
    }

    @Test
    public void testCreateIssue() throws IOException {
        // Caso de sucesso com valores válidos
        Issue issue = new Issue()
                .setProjectKey("YOUR-PROJECT")
                .setSummary("Java Agent Integration")
                .setDescription("Tracking of Java Agent integration in Jira");

        client.createIssue(issue);
        assertTrue(client.getIssues().stream().anyMatch(i -> i.getKey().equals(issue.getKey())));
    }

    @Test
    public void testCreateIssueInvalidProjectKey() throws IOException {
        // Caso de erro (projeto inválido)
        Issue issue = new Issue()
                .setProjectKey("INVALID-PROJECT")
                .setSummary("Java Agent Integration")
                .setDescription("Tracking of Java Agent integration in Jira");

        try {
            client.createIssue(issue);
            fail("Expected an exception to be thrown");
        } catch (IOException e) {
            assertTrue(e.getMessage().contains("Invalid project key"));
        }
    }

    @Test
    public void testCreateIssueNullSummary() throws IOException {
        // Caso de erro (summary nulo)
        Issue issue = new Issue()
                .setProjectKey("YOUR-PROJECT")
                .setSummary(null)
                .setDescription("Tracking of Java Agent integration in Jira");

        try {
            client.createIssue(issue);
            fail("Expected an exception to be thrown");
        } catch (IOException e) {
            assertTrue(e.getMessage().contains("Summary cannot be null"));
        }
    }

    @Test
    public void testCreateIssueInvalidDescription() throws IOException {
        // Caso de erro (description inválida)
        Issue issue = new Issue()
                .setProjectKey("YOUR-PROJECT")
                .setSummary("Java Agent Integration")
                .setDescription(null);

        try {
            client.createIssue(issue);
            fail("Expected an exception to be thrown");
        } catch (IOException e) {
            assertTrue(e.getMessage().contains("Description cannot be null"));
        }
    }

    @Test
    public void testSearchIssuesByTitle() throws IOException {
        // Caso de sucesso com valores válidos
        SearchResult result = client.searchJql("Java Agent");

        if (!result.isEmpty()) {
            for (Issue issue : result.getIssues()) {
                System.out.println("Found issue: " + issue.getKey());
            }
        } else {
            System.out.println("No issues found with the title: Java Agent");
        }
    }

    @Test
    public void testSearchIssuesByTitleInvalidQuery() throws IOException {
        // Caso de erro (query inválida)
        SearchResult result = client.searchJql("INVALID-QUERY");

        assertTrue(result.isEmpty());
    }

    @Test
    public void testAddWorklogEntry() throws IOException {
        // Caso de sucesso com valores válidos
        WorklogEntry worklogEntry = new WorklogEntry()
                .setIssueKey("issue-key-123")
                .setAuthor("John Doe")
                .setDescription("Adding Java Agent integration")
                .setDuration(8.0);

        client.addWorklog(worklogEntry);
        assertTrue(client.getIssues().stream().anyMatch(i -> i.getKey().equals("issue-key-123")));
    }

    @Test
    public void testAddWorklogEntryInvalidIssueKey() throws IOException {
        // Caso de erro (issue key inválida)
        WorklogEntry worklogEntry = new WorklogEntry()
                .setIssueKey("INVALID-ISSUE")
                .setAuthor("John Doe")
                .setDescription("Adding Java Agent integration")
                .setDuration(8.0);

        try {
            client.addWorklog(worklogEntry);
            fail("Expected an exception to be thrown");
        } catch (IOException e) {
            assertTrue(e.getMessage().contains("Invalid issue key"));
        }
    }

    @Test
    public void testAddWorklogEntryNullAuthor() throws IOException {
        // Caso de erro (author nulo)
        WorklogEntry worklogEntry = new WorklogEntry()
                .setIssueKey("issue-key-123")
                .setAuthor(null)
                .setDescription("Adding Java Agent integration")
                .setDuration(8.0);

        try {
            client.addWorklog(worklogEntry);
            fail("Expected an exception to be thrown");
        } catch (IOException e) {
            assertTrue(e.getMessage().contains("Author cannot be null"));
        }
    }

    @Test
    public void testAddWorklogEntryInvalidDescription() throws IOException {
        // Caso de erro (description inválida)
        WorklogEntry worklogEntry = new WorklogEntry()
                .setIssueKey("issue-key-123")
                .setAuthor("John Doe")
                .setDescription(null)
                .setDuration(8.0);

        try {
            client.addWorklog(worklogEntry);
            fail("Expected an exception to be thrown");
        } catch (IOException e) {
            assertTrue(e.getMessage().contains("Description cannot be null"));
        }
    }

    @Test
    public void testAddWorklogEntryInvalidDuration() throws IOException {
        // Caso de erro (duration inválida)
        WorklogEntry worklogEntry = new WorklogEntry()
                .setIssueKey("issue-key-123")
                .setAuthor("John Doe")
                .setDescription("Adding Java Agent integration")
                .setDuration(-1.0);

        try {
            client.addWorklog(worklogEntry);
            fail("Expected an exception to be thrown");
        } catch (IOException e) {
            assertTrue(e.getMessage().contains("Duration cannot be negative"));
        }
    }
}