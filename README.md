![Duitku](/static/description/duitku_icon.png)

Duitku Integration for Odoo payment provider

Requirement
--
1. Make sure below this is installed on your odoo
   * Sales
     - Managing order and quotation
   * Invoicing (Should be automated after install sales)
     - Invoicing for creating invoice on order or for creating a payment link to the customer on Odoo
   * eCommerce
     - Website and eCommerce for payment landing pages
   * Website (Should Be automated after install eCommerce)

2. Odoo version 18 (tested on docker version)
3. Postgre SQL (tested on latest docker version)
4. Python 3.7

Installation
--
For installation to the Odoo, you might download this code. Then, drop the folder to the [addons path](https://www.odoo.com/documentation/18.0/id/search.html?q=addons+path&area=default&check_keywords=yes) (default path on odoo docker `mnt/extra-addons/`), then rename it as **payment_duitku**. After it's done you may follow the steps below.

1. Go to your Apps list on Odoo.
2. Find **Duitku Payment Acquirer**. Then, click install.
3. Go to the Sales/Website/Invoicing/Point of Sale.
4. On the Top menu go to the Configuration
   * (Sales) click Online Payments -> Payment Providers.
   * (Website) click eCommerce -> Payment Providers.
   * (Invoicing) click Online Payments -> Payment Providers.
   * (Point of Sale) click Payment Methods -> Select or Create new -> Online Payment checked -> Payment Providers.
5. On the list of Payment click on **Duitku Payment**.
6. Edit the payment and fill with your Duitku credentials. (If you don't have any credentials you might start from creating project on [Duitku Dashboard](https://dashboard.duitku.com/)).
   - Set payment state as **Enable** for Production and **Test Mode** for sandbox
   - Please fill Duitku credential as the environment that would like to use. 
7. Click save and done.
8. For Point of sales add Duitku Payment to Allowed Providers on the Payment Method.

You've finish the installation process. You might see the Duitku payment on the checkout payment list.
