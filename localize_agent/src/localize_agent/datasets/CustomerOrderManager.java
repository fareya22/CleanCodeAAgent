public class CustomerOrderManager {
    // God Class Example - handles too many responsibilities
    
    // Customer data
    public String customerName;
    public String customerEmail;
    public String customerAddress;
    public String customerPhone;
    
    // Order data
    private int orderId;
    private double totalAmount;
    private String orderStatus;
    
    // Inventory data
    private int availableStock;
    private String warehouseLocation;
    
    // Payment data
    private String paymentMethod;
    private boolean paymentConfirmed;
    
    // Shipping data
    private String shippingAddress;
    private String trackingNumber;
    
    // Feature Envy Example - this method uses OrderItem more than its own class
    public double calculateItemDiscount(OrderItem item) {
        double basePrice = item.getBasePrice();
        int quantity = item.getQuantity();
        String category = item.getCategory();
        
        double discount = 0;
        if (category.equals("Electronics")) {
            discount = basePrice * 0.10;
        } else if (category.equals("Clothing")) {
            discount = basePrice * 0.15;
        }
        
        if (quantity > 5) {
            discount += basePrice * 0.05;
        }
        
        return discount * quantity;
    }
    
    // Complexity Example - too many nested conditions and responsibilities
    public void processCustomerOrder(String customerId, String productId, int quantity) {
        if (customerId != null && !customerId.isEmpty()) {
            if (productId != null && !productId.isEmpty()) {
                if (quantity > 0) {
                    if (availableStock >= quantity) {
                        double price = getProductPrice(productId);
                        if (price > 0) {
                            totalAmount = price * quantity;
                            if (totalAmount > 1000) {
                                totalAmount = totalAmount * 0.9;
                            }
                            availableStock -= quantity;
                            orderStatus = "Processing";
                            
                            // Send email
                            if (customerEmail != null) {
                                String emailBody = "Dear " + customerName + ", your order has been placed.";
                                sendEmail(customerEmail, emailBody);
                            }
                            
                            // Process payment
                            if (paymentMethod.equals("CreditCard")) {
                                if (totalAmount < 5000) {
                                    paymentConfirmed = true;
                                } else {
                                    paymentConfirmed = false;
                                }
                            }
                            
                            // Update shipping
                            if (paymentConfirmed) {
                                trackingNumber = generateTrackingNumber();
                                shippingAddress = customerAddress;
                            }
                        }
                    } else {
                        System.out.println("Insufficient stock");
                    }
                } else {
                    System.out.println("Invalid quantity");
                }
            } else {
                System.out.println("Invalid product ID");
            }
        } else {
            System.out.println("Invalid customer ID");
        }
    }
    
    public void sendEmail(String email, String body) {
        System.out.println("Sending email to: " + email);
    }
    
    public double getProductPrice(String productId) {
        return 100.0;
    }
    
    public String generateTrackingNumber() {
        return "TRACK" + System.currentTimeMillis();
    }
    
    // Information Hiding Issue - exposing internal calculation logic
    public double calculateTotalWithTaxAndShipping() {
        double tax = totalAmount * 0.08;
        double shipping = 15.0;
        if (totalAmount > 500) {
            shipping = 0;
        }
        return totalAmount + tax + shipping;
    }
}

class OrderItem {
    private double basePrice;
    private int quantity;
    private String category;
    
    public double getBasePrice() {
        return basePrice;
    }
    
    public int getQuantity() {
        return quantity;
    }
    
    public String getCategory() {
        return category;
    }
    
    public void setBasePrice(double price) {
        this.basePrice = price;
    }
    
    public void setQuantity(int qty) {
        this.quantity = qty;
    }
    
    public void setCategory(String cat) {
        this.category = cat;
    }
}
