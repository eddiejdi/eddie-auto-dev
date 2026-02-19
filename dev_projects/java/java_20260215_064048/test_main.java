import com.atlassian.jira.issue.Issue;
import com.atlassian.jira.issue.IssueManager;
import com.atlassian.jira.project.Project;
import com.atlassian.jira.project.ProjectManager;
import com.atlassian.jira.service.ServiceContext;
import com.atlassian.jira.user.User;
import com.atlassian.jira.user.UserService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class JavaAgentTest {

    private static final Logger logger = LoggerFactory.getLogger(JavaAgentTest.class);

    @Test
    public void testMonitorAndAlertIssuesWithValidInput() throws Exception {
        // Configurações do Jira
        String jiraUrl = "http://your-jira-url";
        String username = "your-username";
        String password = "your-password";

        try {
            // Autenticação no Jira
            ServiceContext serviceContext = new ServiceContext();
            serviceContext.setUsername(username);
            serviceContext.setPassword(password);

            // Obtenção de serviços do Jira
            IssueManager issueManager = ComponentAccessor.getComponent(IssueManager.class);
            ProjectManager projectManager = ComponentAccessor.getComponent(ProjectManager.class);
            UserService userService = ComponentAccessor.getComponent(UserService.class);

            // Funções de monitoramento e alertas
            User user = userService.getUserByName("your-username");
            if (user == null) {
                throw new RuntimeException("User not found");
            }

            List<Issue> issues = issueManager.getIssuesForUser(user, serviceContext);
            for (Issue issue : issues) {
                // Verifica se há problemas na atividade
                if (issue.getStatus().getName().equals("In Progress") && issue.getPriority().getName().equals("High")) {
                    // Alerta para o usuário
                    sendAlertToUser(user, "High priority issue detected: " + issue.getKey());
                }
            }
        } catch (Exception e) {
            logger.error("Error occurred while monitoring and alerting issues", e);
        }
    }

    @Test(expected = RuntimeException.class)
    public void testMonitorAndAlertIssuesWithInvalidUsername() throws Exception {
        // Configurações do Jira
        String jiraUrl = "http://your-jira-url";
        String username = "invalid-username";
        String password = "your-password";

        try {
            // Autenticação no Jira
            ServiceContext serviceContext = new ServiceContext();
            serviceContext.setUsername(username);
            serviceContext.setPassword(password);

            // Obtenção de serviços do Jira
            IssueManager issueManager = ComponentAccessor.getComponent(IssueManager.class);
            ProjectManager projectManager = ComponentAccessor.getComponent(ProjectManager.class);
            UserService userService = ComponentAccessor.getComponent(UserService.class);

            // Funções de monitoramento e alertas
            User user = userService.getUserByName("your-username");
            if (user == null) {
                throw new RuntimeException("User not found");
            }

            List<Issue> issues = issueManager.getIssuesForUser(user, serviceContext);
            for (Issue issue : issues) {
                // Verifica se há problemas na atividade
                if (issue.getStatus().getName().equals("In Progress") && issue.getPriority().getName().equals("High")) {
                    // Alerta para o usuário
                    sendAlertToUser(user, "High priority issue detected: " + issue.getKey());
                }
            }
        } catch (Exception e) {
            logger.error("Error occurred while monitoring and alerting issues", e);
        }
    }

    @Test(expected = Exception.class)
    public void testMonitorAndAlertIssuesWithNullServiceContext() throws Exception {
        // Configurações do Jira
        String jiraUrl = "http://your-jira-url";
        String username = "your-username";
        String password = "your-password";

        try {
            // Autenticação no Jira
            ServiceContext serviceContext = null;
            serviceContext.setUsername(username);
            serviceContext.setPassword(password);

            // Obtenção de serviços do Jira
            IssueManager issueManager = ComponentAccessor.getComponent(IssueManager.class);
            ProjectManager projectManager = ComponentAccessor.getComponent(ProjectManager.class);
            UserService userService = ComponentAccessor.getComponent(UserService.class);

            // Funções de monitoramento e alertas
            User user = userService.getUserByName("your-username");
            if (user == null) {
                throw new RuntimeException("User not found");
            }

            List<Issue> issues = issueManager.getIssuesForUser(user, serviceContext);
            for (Issue issue : issues) {
                // Verifica se há problemas na atividade
                if (issue.getStatus().getName().equals("In Progress") && issue.getPriority().getName().equals("High")) {
                    // Alerta para o usuário
                    sendAlertToUser(user, "High priority issue detected: " + issue.getKey());
                }
            }
        } catch (Exception e) {
            logger.error("Error occurred while monitoring and alerting issues", e);
        }
    }

    private static void sendAlertToUser(User user, String message) throws Exception {
        // Implemente a lógica de envio de alertas (por exemplo, por e-mail ou SMS)
        logger.info("Sending alert to user {}: {}", user.getName(), message);
    }
}