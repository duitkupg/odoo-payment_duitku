![Duitku](./payment_duitku/static/src/img/duitku_icon.png)

Duitku Integration for Odoo payment provider

Requirement
--
1. Make sure below this is installed on your odoo
   * Website
   * eCommerce
     - Website and eCommerce for payment landing pages
   * Invoicing
     - Invoicing for creating invoice on order or for creating a payment link to the customer on Odoo
   * Sales
     - Managing order and quotation

2. Odoo version 16 (tested on docker version)
3. Postgre SQL (tested on latest docker version)
4. Python 3.7

Installation
--
For installation to the Odoo, you might download this code. Then, drop the folder to the [addons path](https://www.google.com/search?rlz=1C1GCEU_enID969ID969&sxsrf=ALiCzsZONTAyLMHdFUsFG_-kRZb73pxHWQ%3A1660796744026&lei=SL_9YsSWAYje4-EP8-6fuAY&q=odoo%2014%20addons%20path&ved=2ahUKEwjE2uL_xc_5AhUI7zgGHXP3B2cQsKwBKAJ6BAg9EAM&biw=1920&bih=937&dpr=1), then rename it as **payment_duitku**. After it's done you may follow the steps below.

1. Go to your Apps list on Odoo.
2. Find **Duitku Payment Acquirer**. Then, click install.
3. Go to the Website/Invoicing.
4. On the Top menu go to the Configuration -> payments -> Payment Providers.
5. On the list of Payment click on **Duitku Payment**.
6. Edit the payment and fill with your Duitku credentials. (If you don't have any credentials you might start from creating project on [Duitku Dashboard](https://dashboard.duitku.com/)).
   - Set payment state as **Enable** for Production and **Test Mode** for sandbox
   - Please fill Duitku credential as the environment that would like to use. 
7. Click save and done.

You've finish the installation process. You might see the Duitku payment on the checkout payment list.
